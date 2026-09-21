from llvmlite import ir
import llvmlite.binding as llvm
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("source_path", help="path to the .txt file with your code")
parser.add_argument("output_path", nargs="?", default=None, help="path to the .ll file")
parser.add_argument("--tokens", action="store_true", help="print the token stream to stdout")
parser.add_argument("--ast", action="store_true", help="print the AST tree and exit")

args = parser.parse_args()

I32, I8 = ir.IntType(32), ir.IntType(8)

module = ir.Module(name="practice1")
module.triple = llvm.get_default_triple()
main = ir.Function(module, ir.FunctionType(I32, []), name="main")
entry_block = main.append_basic_block("entry")
builder = ir.IRBuilder(entry_block)

printf = ir.Function(module, ir.FunctionType(I32, [ir.PointerType(I8)], var_arg=True), name="printf") # declaration only
text = b"Program exit with result %d\n\0"
fmt = ir.GlobalVariable(module, ir.ArrayType(I8, len(text)), name="fmt")
fmt.linkage, fmt.global_constant = "private", True
fmt.initializer = ir.Constant(ir.ArrayType(I8, len(text)), bytearray(text))

TYPES = {
    "i32": I32,
}

KEYWORDS = {
    "i32": "typename",
    "mut": "specifier",
    "exit": "statement",
}

OPERATORS = {
    "+": builder.add,
    "-": builder.sub,
    "*": builder.mul,
}

def raise_err(error_number, err_line, column, ue_part=""):
    ERRORS = {
        1: "redeclared variable",
        2: "undeclared variable",
        3: "invalid variable name",
        4: "unparsable statement",
        5: "missing exit statement",
        6: "exit must be the last statement",
        7: "unparsable exit statement",
        8: "unsupported operator",
        9: "'{' is not closed before the end of the line",
        10: "unexpected byte",
        11: "unknown type",
        12: "cannot assign to immutable variable"
    }

    msg = ERRORS.get(error_number, "unknown compilation error")
    if error_number in (10,11,12): msg += f" {ue_part}"
    sys.stderr.write(f"compilation error: line {err_line}:{column}: {msg}\n")
    sys.exit(error_number)


class Token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col

    def to_str(self):
        return f"({self.kind}, {self.text}, {self.line}, {self.col})"


def is_alpha(b):
    if (ord("A") <= b <= ord("Z")) or (ord("a") <= b <= ord("z")) or b == ord("_"):
        return True
    return False


def is_digit(b):
    if ord("0") <= b <= ord("9"):
        return True
    return False

def is_operator(b):
    if ord("*") == b or ord("+") == b or ord("-") == b:
        return True
    return False


def lex(data: bytes):
    lexer_lines, tokens = [], []
    state, start, line, col = "START", 0, 1, 1
    open_brace_col = None
    start_col = 1
    i = 0
    while i <= len(data):  # one extra step: the end of input
        b = data[i] if i < len(data) else None

        if state == "START":
            if b is None:
                break
            elif b in (32, 9):
                pass  # space, tab
            elif b == 10: # new line
                if open_brace_col is not None:
                    raise_err(9, line, open_brace_col)
                lexer_lines.append(tokens)
                tokens = []
                line += 1; col = 0
            elif is_alpha(b):
                state, start, start_col = "IDENT", i, col
            elif is_digit(b):
                state, start, start_col = "NUMBER", i, col
            elif b == ord("{"):
                tokens.append(Token("lbrace","{", line, col))
                open_brace_col = col
            elif b == ord("}"):
                tokens.append(Token("rbrace", "}", line, col))
                open_brace_col = None
            elif b == ord(":"):
                state = "ASSIGN"
                start_col = col
            elif is_operator(b):
                tokens.append(Token("operator", chr(b), line, col))
            else:
                raise_err(10, line, col, ue_part = chr(b))

        elif state == "IDENT":
            if b is not None and (is_alpha(b) or is_digit(b)):
                pass
            else:
                word = data[start:i]
                tokens.append(Token(KEYWORDS.get(word.decode(), "ident"), word.decode(), line, start_col))
                state = "START"; continue  # re-read this byte in START

        elif state == "NUMBER":
            if b is not None and is_digit(b):
                pass#braces
            elif b is not None and is_alpha(b):
                raise_err(10, line, col, ue_part = chr(b))
            else:
                num = data[start:i]
                tokens.append(Token(KEYWORDS.get(num.decode(), "constant"), num.decode(), line, start_col))
                state = "START"; continue  # re-read this byte in START

        elif state == "ASSIGN":
            if b == ord("="):
                tokens.append(Token("assignment", ":=", line, start_col))
                state = "START"
            else:
                raise_err(10, line, col, ue_part = chr(b))

        i += 1; col += 1
    if tokens: lexer_lines.append(tokens)
    return lexer_lines

class ProgramNode:
    def __init__(self, line, col, stmts, exit_node):
        self.line, self.col, self.stmts, self.exit = line, col, stmts, exit_node
    
    def dump(self, indent=0):
        print(" " * indent + "Program")
        for stmt in self.stmts:
            stmt.dump(indent + 2)
        if self.exit:
            self.exit.dump(indent + 2)


class DeclNode:
    def __init__(self, line, col, name: str, mutable: bool, init):
        self.line, self.col, self.name, self.mutable, self.init = line, col, name, mutable, init
    
    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"
        print(" " * indent + f"Decl {self.name} {kind}")
        self.init.dump(indent + 2)


class AssignNode:
    def __init__(self, line, col, name, value):
        self.line, self.col, self.name, self.value = line, col, name, value
    
    def dump(self, indent=0):
        print(" " * indent + f"Assign {self.name}")
        self.value.dump(indent + 2)


class BinOpNode:
    def __init__(self, line, col, op, left, right):
        self.line, self.col, self.op, self.left, self.right = line, col, op, left, right
    
    def dump(self, indent=0):
        print(" " * indent + f"BinOp {self.op}")
        self.left.dump(indent + 2)
        self.right.dump(indent + 2)


class VarNode:
    def __init__(self, line, col, name):
        self.line, self.col, self.name = line, col, name
    
    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")


class ConstNode:
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val
    
    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")


class ExitNode:
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val
    
    def dump(self, indent=0):
        print(" " * indent + "Exit")
        self.val.dump(indent + 2)

class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.toks = []
        self.pos = 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def eat(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def get_pos_info(self):
        tok = self.peek()
        if tok:
            return tok.line, tok.col
        if self.toks:
            last = self.toks[-1]
            return last.line, last.col + len(last.text)
        return 1, 1

    def parse_program(self):
        stmts = []
        exit_node = None
        has_exit = False

        for line_toks in self.lines:
            if not line_toks:
                continue
            self.toks, self.pos = line_toks, 0

            if has_exit:
                line, col = self.get_pos_info()
                raise_err(6, line, col)

            tok = self.peek()
            if tok.kind == "statement" and tok.text == "exit":
                exit_node = self.parse_exit()
                has_exit = True
            else:
                stmt_node = self.parse_statement()
                stmts.append(stmt_node)

            if self.peek() is not None:
                line, col = self.get_pos_info()
                err_code = 7 if has_exit else 4
                raise_err(err_code, line, col)

        if not has_exit:
            err_line = self.lines[-1][-1].line if (self.lines and self.lines[-1]) else 1
            raise_err(5, err_line, 1)

        first_line = stmts[0].line if stmts else (exit_node.line if exit_node else 1)
        first_col = stmts[0].col if stmts else (exit_node.col if exit_node else 1)
        return ProgramNode(first_line, first_col, stmts, exit_node)

    def parse_statement(self):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_err(4, line, col)

        if tok.kind == "typename" and tok.text == "i32":
            return self.parse_decl()
        elif tok.kind == "ident":
            return self.parse_assignment()
        else:
            raise_err(4, tok.line, tok.col)

    def parse_decl(self):
        i32_tok = self.eat()  # "i32"
        mutable = False

        tok = self.peek()
        if tok is not None and tok.kind == "specifier" and tok.text == "mut":
            self.eat()
            mutable = True

        name_tok = self.peek()
        if name_tok is None or name_tok.kind != "ident":
            line, col = self.get_pos_info()
            raise_err(4, line, col)
        name_tok = self.eat()

        lbrace_tok = self.peek()
        if lbrace_tok is None or lbrace_tok.kind != "lbrace":
            line, col = self.get_pos_info()
            raise_err(4, line, col)
        self.eat()

        init = self.parse_value(is_exit=False)

        rbrace_tok = self.peek()
        if rbrace_tok is None or rbrace_tok.kind != "rbrace":
            line, col = self.get_pos_info()
            raise_err(4, line, col)
        self.eat()

        return DeclNode(i32_tok.line, i32_tok.col, name_tok.text, mutable, init)

    def parse_assignment(self):
        var_tok = self.eat()  # ident

        assign_tok = self.peek()
        if assign_tok is None or assign_tok.kind != "assignment":
            line, col = self.get_pos_info()
            raise_err(4, line, col)
        self.eat()

        value = self.parse_value(is_exit=False)
        return AssignNode(var_tok.line, var_tok.col, var_tok.text, value)

    def parse_exit(self):
        exit_tok = self.eat()  # "exit"
        val = self.parse_operand(is_exit=True)
        return ExitNode(exit_tok.line, exit_tok.col, val)

    def parse_value(self, is_exit=False):
        # value ::= operand [ op operand ]
        left = self.parse_operand(is_exit)
        tok = self.peek()
        if tok is not None and tok.kind == "operator":
            op_tok = self.eat()
            right = self.parse_operand(is_exit)
            return BinOpNode(op_tok.line, op_tok.col, op_tok.text, left, right)
        return left

    def parse_operand(self, is_exit=False):
        # operand ::= ident | constant
        tok = self.peek()
        err_code = 7 if is_exit else 4

        if tok is None:
            line, col = self.get_pos_info()
            raise_err(err_code, line, col)

        if tok.kind == "ident":
            self.eat()
            return VarNode(tok.line, tok.col, tok.text)
        elif tok.kind == "constant":
            self.eat()
            return ConstNode(tok.line, tok.col, tok.text)
        else:
            raise_err(err_code, tok.line, tok.col)
    


with open(args.source_path, "rb") as f:
    file_bytes = f.read()

lines = lex(file_bytes)

if args.tokens:
    for line in lines:
        for token in line:
            print(token.to_str() + " ")
        print()

parser_obj = Parser(lines)
ast = parser_obj.parse_program()

if args.ast:
    ast.dump()

if args.output_path:
    with open(args.output_path, "w") as out_f:
        out_f.write(str(module))