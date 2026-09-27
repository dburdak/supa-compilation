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
    if error_number in (1, 2, 10, 11, 12) and ue_part:
        msg += f" {ue_part}"
    sys.stderr.write(f"compilation error: line {err_line}:{column}: {msg}\n")
    sys.exit(error_number)

def raise_syntax_err(line, col, msg):
    sys.stderr.write(f"compilation error: line {line}:{col}: {msg}\n")
    sys.exit(13)


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

    def accept(self, visitor):
        return visitor.visit_program(self)


class DeclNode:
    def __init__(self, line, col, name: str, mutable: bool, init):
        self.line, self.col, self.name, self.mutable, self.init = line, col, name, mutable, init
    
    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"
        print(" " * indent + f"Decl {self.name} {kind}")
        self.init.dump(indent + 2)
    
    def accept(self, visitor):
        return visitor.visit_decl(self)


class AssignNode:
    def __init__(self, line, col, name, value):
        self.line, self.col, self.name, self.value = line, col, name, value
    
    def dump(self, indent=0):
        print(" " * indent + f"Assign {self.name}")
        self.value.dump(indent + 2)
    
    def accept(self, visitor):
        return visitor.visit_assign(self)


class BinOpNode:
    def __init__(self, line, col, op, left, right):
        self.line, self.col, self.op, self.left, self.right = line, col, op, left, right
    
    def dump(self, indent=0):
        print(" " * indent + f"BinOp {self.op}")
        self.left.dump(indent + 2)
        self.right.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_binop(self)


class VarNode:
    def __init__(self, line, col, name):
        self.line, self.col, self.name = line, col, name
    
    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")
    
    def accept(self, visitor):
        return visitor.visit_var(self)


class ConstNode:
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val
    
    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")

    def accept(self, visitor):
        return visitor.visit_const(self)

class ExitNode:
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val
    
    def dump(self, indent=0):
        print(" " * indent + "Exit")
        self.val.dump(indent + 2)
    
    def accept(self, visitor):
        return visitor.visit_exit(self)

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
    
    def expect(self, kind, what_expected):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_syntax_err(line, col, f"expected {what_expected}, found end of line")
        if tok.kind != kind:
            raise_syntax_err(tok.line, tok.col, f"expected {what_expected}, got '{tok.text}'")
        return self.eat()

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
                raise_err(6, line, col)  # Exit must be the last statement

            tok = self.peek()
            if tok.kind == "statement" and tok.text == "exit":
                exit_node = self.parse_exit()
                has_exit = True
            else:
                stmt_node = self.parse_statement()
                stmts.append(stmt_node)

            if self.peek() is not None:
                line, col = self.get_pos_info()
                if has_exit:
                    raise_err(7, line, col)  # Unparsable exit statement
                else:
                    leftover = self.peek()
                    raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after statement")

        first_line = stmts[0].line if stmts else (exit_node.line if exit_node else 1)
        first_col = stmts[0].col if stmts else (exit_node.col if exit_node else 1)
        return ProgramNode(first_line, first_col, stmts, exit_node)

    def parse_statement(self):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_syntax_err(line, col, "expected statement, found end of line")

        if tok.kind == "typename" and tok.text == "i32":
            return self.parse_decl()
        elif tok.kind == "ident":
            return self.parse_assignment()
        else:
            raise_syntax_err(tok.line, tok.col, f"cannot start a statement with '{tok.text}'")

    def parse_decl(self):
        i32_tok = self.eat()  # "i32"
        mutable = False

        tok = self.peek()
        if tok is not None and tok.kind == "specifier" and tok.text == "mut":
            self.eat()
            mutable = True

        name_tok = self.expect("ident", "variable name")
        self.expect("lbrace", "'{'")

        init = self.parse_expr()

        self.expect("rbrace", "'}'")

        return DeclNode(name_tok.line, name_tok.col, name_tok.text, mutable, init)

    def parse_assignment(self):
        var_tok = self.eat()  # ident
        self.expect("assignment", "':='")
        value = self.parse_expr()
        return AssignNode(var_tok.line, var_tok.col, var_tok.text, value)

    def parse_exit(self):
        exit_tok = self.eat()  # "exit"
        val = self.parse_operand(is_exit=True)
        return ExitNode(exit_tok.line, exit_tok.col, val)

    def parse_expr(self):
        # expr ::= term { ("+" | "-") term }
        node = self.parse_term()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "+-":
            op_tok = self.eat()
            # Будуємо лівоасоціативне дерево BinOpNode
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_term())
        return node

    def parse_term(self):
        # term ::= operand { "*" operand }
        node = self.parse_operand()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text == "*":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_operand())
        return node

    def parse_operand(self, is_exit=False):
        # operand ::= ident | number
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

    def parse_operand(self, is_exit=False):
        # operand ::= ident | constant
        tok = self.peek()

        if tok is None:
            line, col = self.get_pos_info()
            if is_exit:
                raise_err(7, line, col)
            else:
                raise_syntax_err(line, col, "expected constant or variable, found end of line")

        if tok.kind == "ident":
            self.eat()
            return VarNode(tok.line, tok.col, tok.text)
        elif tok.kind == "constant":
            self.eat()
            return ConstNode(tok.line, tok.col, tok.text)
        else:
            if is_exit:
                raise_err(7, tok.line, tok.col)
            else:
                raise_syntax_err(tok.line, tok.col, f"expected constant or variable, got '{tok.text}'")

class CodeGenVisitor:
    def __init__(self, builder, printf_func, fmt_global):
        self.builder = builder
        self.printf = printf_func
        self.fmt_global = fmt_global
        # Symbol table: name -> (alloca_ptr, is_mutable)
        self.symbols = {}

    def visit_program(self, node):
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)
        else:
            err_line = node.stmts[-1].line if node.stmts else node.line
            raise_err(5, err_line, 1)


    def visit_decl(self, node):
        if node.name in self.symbols:
            raise_err(1, node.line, node.col, ue_part=f"'{node.name}'")  # redeclared variable
        
        init_val = node.init.accept(self)
        ptr = self.builder.alloca(I32, name=node.name)
        self.builder.store(init_val, ptr)
        self.symbols[node.name] = (ptr, node.mutable)

    def visit_assign(self, node):
        if node.name not in self.symbols:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")  # undeclared variable
        
        ptr, is_mutable = self.symbols[node.name]
        if not is_mutable:
            raise_err(12, node.line, node.col, ue_part=f"'{node.name}'")  # cannot assign to const

        val = node.value.accept(self)
        self.builder.store(val, ptr)

    def visit_exit(self, node):
        val = node.val.accept(self)
        # GEP to get pointer to format string
        fmt_ptr = self.builder.gep(self.fmt_global, [ir.Constant(I32, 0), ir.Constant(I32, 0)])
        self.builder.call(self.printf, [fmt_ptr, val])
        self.builder.ret(ir.Constant(I32, 0))

    def visit_binop(self, node):
        left_val = node.left.accept(self)
        right_val = node.right.accept(self)

        if node.op == "+":
            return self.builder.add(left_val, right_val)
        elif node.op == "-":
            return self.builder.sub(left_val, right_val)
        elif node.op == "*":
            return self.builder.mul(left_val, right_val)
        else:
            raise_err(8, node.line, node.col)  # unsupported operator

    def visit_var(self, node):
        if node.name not in self.symbols:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")  # undeclared variable
        
        ptr, _ = self.symbols[node.name]
        return self.builder.load(ptr, name=node.name)

    def visit_const(self, node):
        return ir.Constant(I32, int(node.val))


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
    sys.exit(0)

codegen = CodeGenVisitor(builder, printf, fmt)
ast.accept(codegen)

if args.output_path:
    with open(args.output_path, "w") as out_f:
        out_f.write(str(module))