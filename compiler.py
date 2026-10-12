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

I32, I8, I64 = ir.IntType(32), ir.IntType(8), ir.IntType(64)
I1 = ir.IntType(1)

module = ir.Module(name="practice1")
module.triple = llvm.get_default_triple()
main = ir.Function(module, ir.FunctionType(I32, []), name="main")
entry_block = main.append_basic_block("entry")
builder = ir.IRBuilder(entry_block)

printf = ir.Function(module, ir.FunctionType(I32, [ir.PointerType(I8)], var_arg=True), name="printf")
text = b"Program exit with result %lld\n\0"
fmt = ir.GlobalVariable(module, ir.ArrayType(I8, len(text)), name="fmt")
fmt.linkage, fmt.global_constant = "private", True
fmt.initializer = ir.Constant(ir.ArrayType(I8, len(text)), bytearray(text))

text_bool = b"Program exit with result %s\n\0"
fmt_bool = ir.GlobalVariable(module, ir.ArrayType(I8, len(text_bool)), name="fmt_bool")
fmt_bool.linkage, fmt_bool.global_constant = "private", True
fmt_bool.initializer = ir.Constant(ir.ArrayType(I8, len(text_bool)), bytearray(text_bool))

true_str = b"true\0"
fmt_true = ir.GlobalVariable(module, ir.ArrayType(I8, len(true_str)), name="true_str")
fmt_true.linkage, fmt_true.global_constant = "private", True
fmt_true.initializer = ir.Constant(ir.ArrayType(I8, len(true_str)), bytearray(true_str))

false_str = b"false\0"
fmt_false = ir.GlobalVariable(module, ir.ArrayType(I8, len(false_str)), name="false_str")
fmt_false.linkage, fmt_false.global_constant = "private", True
fmt_false.initializer = ir.Constant(ir.ArrayType(I8, len(false_str)), bytearray(false_str))

TYPES = {
    "i32": I32,
    "i64": I64,
    "bool": I1,
}

KEYWORDS = {
    "i32": "typename",
    "i64": "typename",
    "bool": "typename",
    "true": "bool_literal",
    "false": "bool_literal",
    "mut": "specifier",
    "exit": "statement",
    "struct": "keyword",
    "fn": "keyword",
    "if": "keyword",
    "else": "keyword",
    "while": "keyword",

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
        12: "cannot assign to immutable variable",
        13: "expected '==' (a single '=' is not an operator)",
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
    if ord("*") == b or ord("+") == b:
        return True
    return False


def lex(data: bytes):
    lexer_lines, tokens = [], []
    state, start, line, col = "START", 0, 1, 1
    start_col = 1
    i = 0
    while i <= len(data):
        b = data[i] if i < len(data) else None

        if state == "START":
            if b is None:
                break
            elif b in (32, 9):
                pass
            elif b == 10:
                lexer_lines.append(tokens)
                tokens = []
                line += 1; col = 0
            elif is_alpha(b):
                state, start, start_col = "IDENT", i, col
            elif is_digit(b):
                state, start, start_col = "NUMBER", i, col
            elif b == ord("{"):
                tokens.append(Token("lbrace", "{", line, col))
            elif b == ord("}"):
                tokens.append(Token("rbrace", "}", line, col))
                open_brace_col = None
            elif b == ord("("):
                tokens.append(Token("lparen", "(", line, col))
            elif b == ord(")"):
                tokens.append(Token("rparen", ")", line, col))
            elif b == ord(","):
                tokens.append(Token("comma", ",", line, col))
            elif b == ord("-"):
                state = "MINUS"
                start_col = col
            elif b == ord(":"):
                state = "ASSIGN"
                start_col = col
            elif b == ord("!"):
                state = "NOTEQUAL"
                start_col = col
            elif b == ord("="):
                state = "EQUAL"
                start_col = col
            elif is_operator(b):
                tokens.append(Token("operator", chr(b), line, col))
            else:
                raise_err(10, line, col, ue_part=chr(b))

        elif state == "IDENT":
            if b is not None and (is_alpha(b) or is_digit(b)):
                pass
            else:
                word = data[start:i]
                tokens.append(Token(KEYWORDS.get(word.decode(), "ident"), word.decode(), line, start_col))
                state = "START"; continue

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
            elif b is None:
                raise_err(10, line, col, ue_part="'end of file'")
            else:
                raise_err(10, line, col, ue_part=chr(b))

        elif state == "EQUAL":
            if b == ord("="):
                tokens.append(Token("comparison","==", line, start_col))
                state = "START"                
            elif b is None:
                raise_err(13, line, start_col)
            else:
                raise_err(13, line, start_col)
        
        elif state == "NOTEQUAL":
            if b == ord("="):
                tokens.append(Token("comparison","!=", line, start_col))
                state = "START"
            else:
                # bare '!' — re-read the current byte in START
                tokens.append(Token("operator", "!", line, start_col))
                state = "START"
                continue

        elif state == "MINUS":
            if b == ord(">"):
                tokens.append(Token("arrow", "->", line, start_col))
                state = "START"
            else:
                tokens.append(Token("operator", "-", line, start_col))
                state = "START"
                continue

        i += 1
        col += 1

    if tokens:
        lexer_lines.append(tokens)
    return lexer_lines


class Node:
    def __init__(self, line, col):
        self.line, self.col = line, col

class ProgramNode(Node):
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

class StmtNode(Node):
    pass

class ExprNode(Node):
    pass

class FieldDef:
    def __init__(self, line: int, col: int, type_name: str, mutable: bool, name: str):
        self.line = line
        self.col = col
        self.type_name = type_name
        self.mutable = mutable
        self.name = name


class StructDefNode(StmtNode):
    def __init__(self, line: int, col: int, name: str, fields: list):
        self.line = line
        self.col = col
        self.name = name
        self.fields = fields

    def dump(self, indent=0):
        print(" " * indent + f"Struct {self.name}")
        for f in self.fields:
            kind = "mut" if f.mutable else "const"
            print(" " * (indent + 2) + f"Field {f.name} {f.type_name} {kind}")

    def accept(self, visitor):
        return visitor.visit_struct_def(self)


class DeclNode(StmtNode):
    def __init__(self, line, col, type_name: str, name: str, mutable: bool, init, inits=None):
        self.line, self.col = line, col
        self.type_name = type_name
        self.name = name
        self.mutable = mutable
        self.init = init
        self.inits = inits if inits is not None else ([init] if not isinstance(init, list) else init)

    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"
        print(" " * indent + f"Decl {self.name} {self.type_name} {kind}")
        if isinstance(self.init, list):
            for e in self.init:
                e.dump(indent + 2)
        else:
            self.init.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_decl(self)


class AssignNode(StmtNode):
    def __init__(self, line, col, name, value):
        self.line, self.col, self.name, self.value = line, col, name, value

    def dump(self, indent=0):
        print(" " * indent + f"Assign {self.name}")
        self.value.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_assign(self)


class BinOpNode(ExprNode):
    def __init__(self, line, col, op, left, right):
        self.line, self.col, self.op, self.left, self.right = line, col, op, left, right

    def dump(self, indent=0):
        print(" " * indent + f"BinOp {self.op}")
        self.left.dump(indent + 2)
        self.right.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_binop(self)


class VarNode(ExprNode):
    def __init__(self, line, col, name):
        self.line, self.col, self.name = line, col, name

    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")

    def accept(self, visitor):
        return visitor.visit_var(self)


class ConstNode(ExprNode):
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val

    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")

    def accept(self, visitor):
        return visitor.visit_const(self)


class BoolNode(ExprNode):
    """AST node for boolean literals: true / false."""
    def __init__(self, line, col, val: bool):
        self.line, self.col, self.val = line, col, val

    def dump(self, indent=0):
        print(" " * indent + f"Bool {'true' if self.val else 'false'}")

    def accept(self, visitor):
        return visitor.visit_bool(self)


class NotNode(ExprNode):
    def __init__(self, line, col, operand):
        self.line, self.col, self.operand = line, col, operand

    def dump(self, indent=0):
        print(" " * indent + "Not")
        self.operand.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_not(self)


class BlockNode(Node):
    def __init__(self, line, col, stmts, exit_node = None):
        self.line, self.col = line, col
        self.stmts = stmts
        self.exit = exit_node

    def dump(self, indent=0):
        print(" " * indent + "Block")
        for s in self.stmts:
            s.dump(indent + 2)
        if self.exit:
            self.exit.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_block(self)


class IfNode(StmtNode):
    def __init__(self, line, col, condition, then_block, else_block = None):
        self.line, self.col = line, col
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def dump(self, indent=0):
        print(" " * indent + "If")
        self.condition.dump(indent + 2)
        self.then_block.dump(indent + 2)
        if self.else_block:
            self.else_block.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_if(self)


class WhileNode(StmtNode):
    def __init__(self, line, col, condition, body_block):
        self.line, self.col = line, col
        self.condition = condition
        self.body_block = body_block

    def dump(self, indent=0):
        print(" " * indent + "While")
        self.condition.dump(indent + 2)
        self.body_block.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_while(self)


class ExitNode(Node):
    def __init__(self, line, col, val):
        self.line, self.col, self.val = line, col, val

    def dump(self, indent=0):
        print(" " * indent + "Exit")
        self.val.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_exit(self)


class Param:
    def __init__(self, line, col, type_name, name):
        self.line, self.col, self.type_name, self.name = line, col, type_name, name


class FnDeclNode(StmtNode):
    def __init__(self, line, col, name, params, ret_type, body):
        self.line, self.col = line, col
        self.name = name          # str
        self.params = params      # list[Param]
        self.ret_type = ret_type  # str
        self.body = body          # BlockNode

    def dump(self, indent=0):
        params_str = ", ".join(f"{p.type_name} {p.name}" for p in self.params)
        print(" " * indent + f"FnDecl {self.name}({params_str}) -> {self.ret_type}")
        self.body.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_fn_decl(self)


class FnCallNode(ExprNode):
    def __init__(self, line, col, name, args):
        self.line, self.col = line, col
        self.name = name   # str
        self.args = args   # list[ExprNode]

    def dump(self, indent=0):
        print(" " * indent + f"FnCall {self.name}")
        for a in self.args:
            a.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_fn_call(self)


class BlockNode(Node):
    """A block: { NL stmts exit NL } — used inside functions and if/while."""
    def __init__(self, line, col, stmts, exit_node):
        self.line, self.col = line, col
        self.stmts = stmts          # list of statement nodes
        self.exit_node = exit_node  # ExitNode or None

    def dump(self, indent=0):
        print(" " * indent + "Block")
        for s in self.stmts:
            s.dump(indent + 2)
        if self.exit_node:
            self.exit_node.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_block(self)


class IfNode(StmtNode):
    def __init__(self, line, col, cond, then_block, else_block):
        self.line, self.col = line, col
        self.cond = cond               # ExprNode
        self.then_block = then_block   # BlockNode
        self.else_block = else_block   # BlockNode or None

    def dump(self, indent=0):
        print(" " * indent + "If")
        self.cond.dump(indent + 2)
        self.then_block.dump(indent + 2)
        if self.else_block:
            print(" " * (indent + 2) + "Else")
            self.else_block.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_if(self)


class WhileNode(StmtNode):
    def __init__(self, line, col, cond, body):
        self.line, self.col = line, col
        self.cond = cond   # ExprNode
        self.body = body   # BlockNode

    def dump(self, indent=0):
        print(" " * indent + "While")
        self.cond.dump(indent + 2)
        self.body.dump(indent + 2)

    def accept(self, visitor):
        return visitor.visit_while(self)



class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.toks = []
        self.pos = 0
        self.line_pos = 0

    def peek_line(self):
        while self.line_pos < len(self.lines) and not self.lines[self.line_pos]:
            self.line_pos += 1
        return self.lines[self.line_pos] if self.line_pos < len(self.lines) else None

    def next_line(self):
        while self.line_pos < len(self.lines) and not self.lines[self.line_pos]:
            self.line_pos += 1
        if self.line_pos < len(self.lines):
            toks = self.lines[self.line_pos]
            self.line_pos += 1
            self.toks, self.pos = toks, 0
            return True
        self.toks, self.pos = [], 0
        return False

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

    def expect_eol(self):
        if self.peek() is not None:
            tok = self.peek()
            raise_syntax_err(tok.line, tok.col,
                             f"unexpected '{tok.text}' after statement")

    # ── top-level ──────────────────────────────────────────────────────
    def parse_program(self):
        stmts = []
        while self.peek_line() is not None and not (
            self.peek_line()[0].kind == "statement" and self.peek_line()[0].text == "exit"
        ):
            self.next_line()
            stmt_node = self.parse_statement()
            stmts.append(stmt_node)
            # if/block statements already consumed all their lines;
            # single-line statements: check nothing is left
            if not isinstance(stmt_node, (IfNode, WhileNode)):
                self.expect_eol()

        nxt = self.peek_line()
        if nxt is None:
            err_line = self.lines[-1][-1].line if (self.lines and self.lines[-1]) else 1
            raise_err(5, err_line, 1)

        self.next_line()
        exit_node = self.parse_exit()
        self.expect_eol()

        if self.peek_line() is not None:
            trailing = self.peek_line()
            raise_err(6, trailing[0].line, trailing[0].col)

        first_line = stmts[0].line if stmts else (exit_node.line if exit_node else 1)
        first_col  = stmts[0].col  if stmts else (exit_node.col  if exit_node else 1)
        return ProgramNode(first_line, first_col, stmts, exit_node)

    def parse_statement(self, is_top_level=True, inside_fn=False):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_syntax_err(line, col, "expected statement, found end of line")

        if tok.kind == "keyword" and tok.text == "struct":
            if not is_top_level:
                raise_syntax_err(tok.line, tok.col, "struct declaration not allowed inside a function body")
            return self.parse_struct_def()
        elif tok.kind == "keyword" and tok.text == "fn":
            if not is_top_level:
                raise_syntax_err(tok.line, tok.col, "function declaration not allowed inside a function body")
            return self.parse_fn_decl()
        elif tok.kind == "keyword" and tok.text == "if":
            return self.parse_if(inside_fn=inside_fn)
        elif tok.kind == "keyword" and tok.text == "while":
            return self.parse_while(inside_fn=inside_fn)
        elif tok.kind == "typename":
            return self.parse_decl()
        elif tok.kind == "ident":
            if self.pos + 1 < len(self.toks):
                next_tok = self.toks[self.pos + 1]
                if next_tok.kind == "specifier" and next_tok.text == "mut":
                    return self.parse_decl()
                if next_tok.kind == "ident":
                    return self.parse_decl()
            return self.parse_assignment()
        elif tok.kind == "keyword" and tok.text == "if":
            return self.parse_if()
        elif tok.kind == "keyword" and tok.text == "while":
            return self.parse_while()
        else:
            raise_syntax_err(tok.line, tok.col, f"cannot start a statement with '{tok.text}'")

    def parse_struct_def(self):
        struct_tok = self.eat()  # "struct"
        name_tok = self.expect("ident", "struct name")
        if self.peek() is not None:
            leftover = self.peek()
            raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after struct name")

        nxt = self.peek_line()
        if nxt is None:
            raise_syntax_err(name_tok.line, name_tok.col, "expected '{', found end of file")
        if len(nxt) != 1 or nxt[0].kind != "lbrace":
            raise_syntax_err(nxt[0].line, nxt[0].col, f"expected '{{', got '{nxt[0].text}'")
        self.next_line()
        lbrace_tok = self.eat()

        fields = []
        field_names = set()
        while True:
            nxt = self.peek_line()
            if nxt is None:
                raise_syntax_err(lbrace_tok.line, lbrace_tok.col, "struct body opened here is never closed")
            if len(nxt) == 1 and nxt[0].kind == "rbrace":
                self.next_line()
                self.eat()  # '}'
                break

            self.next_line()
            type_tok = self.peek()
            if type_tok is None:
                line, col = self.get_pos_info()
                raise_syntax_err(line, col, "expected field declaration, found end of line")
            if type_tok.kind not in ("typename", "ident"):
                raise_syntax_err(type_tok.line, type_tok.col, f"expected field type, got '{type_tok.text}'")
            self.eat()

            mutable = False
            tok = self.peek()
            if tok is not None and tok.kind == "specifier" and tok.text == "mut":
                self.eat()
                mutable = True

            fname_tok = self.expect("ident", "field name")
            if fname_tok.text in field_names:
                raise_err(1, fname_tok.line, fname_tok.col, ue_part=f"'{fname_tok.text}'")
            field_names.add(fname_tok.text)

            if self.peek() is not None:
                leftover = self.peek()
                raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after field declaration")

            fields.append(FieldDef(type_tok.line, type_tok.col, type_tok.text, mutable, fname_tok.text))

        if not fields:
            raise_syntax_err(lbrace_tok.line, lbrace_tok.col, "struct must have at least one field")

        return StructDefNode(struct_tok.line, struct_tok.col, name_tok.text, fields)

    def parse_decl(self):
        type_tok = self.eat()  # "i32" | "i64" | "bool" | struct name ident
        type_name = type_tok.text
        mutable = False

        tok = self.peek()
        if tok is not None and tok.kind == "specifier" and tok.text == "mut":
            self.eat()
            mutable = True

        name_tok = self.expect("ident", "variable name")
        self.expect("lbrace", "'{'")

        inits = [self.parse_expr()]
        while (tok := self.peek()) is not None and tok.kind == "comma":
            self.eat()
            inits.append(self.parse_expr())

        self.expect("rbrace", "'}'")

        init_val = inits[0] if len(inits) == 1 else inits
        return DeclNode(name_tok.line, name_tok.col, type_name, name_tok.text, mutable, init_val, inits=inits)

    def parse_assignment(self):
        var_tok = self.eat()  # ident
        self.expect("assignment", "':='")
        value = self.parse_expr()
        return AssignNode(var_tok.line, var_tok.col, var_tok.text, value)

    def parse_exit(self):
        exit_tok = self.eat()  # "exit"
        # If nothing follows on the same line, raise "unparsable exit statement"
        tok = self.peek()
        if tok is None:
            raise_err(7, exit_tok.line, exit_tok.col + len(exit_tok.text))
        val = self.parse_expr()
        return ExitNode(exit_tok.line, exit_tok.col, val)

    def parse_fn_decl(self):
        fn_tok = self.eat()  # "fn"
        name_tok = self.expect("ident", "function name")
        self.expect("assignment", "':='")
        self.expect("lparen", "'('")

        params = []
        param_names = set()
        if self.peek() is not None and self.peek().kind != "rparen":
            params = self.parse_param_list(param_names)

        self.expect("rparen", "')'")
        self.expect("arrow", "'->'")

        ret_tok = self.peek()
        if ret_tok is None or ret_tok.kind not in ("typename", "ident"):
            line, col = self.get_pos_info()
            raise_syntax_err(line, col, "expected return type")
        self.eat()

        if self.peek() is not None:
            leftover = self.peek()
            raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after function signature")

        body = self.parse_block(inside_fn=True, requires_exit=True)
        return FnDeclNode(fn_tok.line, fn_tok.col, name_tok.text, params, ret_tok.text, body)

    def parse_param_list(self, param_names):
        params = []
        while True:
            type_tok = self.peek()
            if type_tok is None or type_tok.kind not in ("typename", "ident"):
                line, col = self.get_pos_info()
                raise_syntax_err(line, col, "expected parameter type")
            self.eat()
            name_tok = self.expect("ident", "parameter name")
            if name_tok.text in param_names:
                raise_err(1, name_tok.line, name_tok.col, ue_part=f"'{name_tok.text}'")
            param_names.add(name_tok.text)
            params.append(Param(type_tok.line, type_tok.col, type_tok.text, name_tok.text))
            if self.peek() is not None and self.peek().kind == "comma":
                self.eat()
            else:
                break
        return params

    def parse_block(self, inside_fn=False, requires_exit=False):
        """Parse: '{' NL { statement } [ exit NL ] '}' NL
        requires_exit=True means the block MUST end with exit (fn body).
        inside_fn means we're inside a fn body (affects nested decls).
        """
        nxt = self.peek_line()
        if nxt is None:
            raise_syntax_err(0, 0, "expected '{', found end of file")
        if len(nxt) != 1 or nxt[0].kind != "lbrace":
            raise_syntax_err(nxt[0].line, nxt[0].col, f"expected '{{', got '{nxt[0].text}'")
        self.next_line()
        lbrace_tok = self.eat()

        stmts = []
        exit_node = None
        has_exit = False

        while True:
            nxt = self.peek_line()
            if nxt is None:
                raise_syntax_err(lbrace_tok.line, lbrace_tok.col, "block opened here is never closed")
            if len(nxt) == 1 and nxt[0].kind == "rbrace":
                self.next_line()
                self.eat()  # '}'
                break

            self.next_line()
            tok = self.peek()

            if tok is None:
                continue

            if tok.kind == "statement" and tok.text == "exit":
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                exit_node = self.parse_exit()
                has_exit = True
                # check nothing follows exit on the same line
                if self.peek() is not None:
                    leftover = self.peek()
                    raise_err(7, leftover.line, leftover.col)
                # next must be '}'
                nxt2 = self.peek_line()
                if nxt2 is None or not (len(nxt2) == 1 and nxt2[0].kind == "rbrace"):
                    if nxt2 is not None:
                        raise_err(6, nxt2[0].line, nxt2[0].col)
                    else:
                        raise_syntax_err(lbrace_tok.line, lbrace_tok.col, "block opened here is never closed")
                self.next_line()
                self.eat()  # '}'
                break
            else:
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                stmt = self.parse_statement(is_top_level=False, inside_fn=inside_fn)
                stmts.append(stmt)
                if self.peek() is not None:
                    leftover = self.peek()
                    raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after statement")

        if requires_exit and not has_exit:
            raise_err(5, lbrace_tok.line, lbrace_tok.col)

        return BlockNode(lbrace_tok.line, lbrace_tok.col, stmts, exit_node)

    def parse_if(self, inside_fn=False):
        if_tok = self.eat()  # "if"
        cond = self.parse_expr()
        if self.peek() is not None:
            leftover = self.peek()
            raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after if condition")
        then_block = self.parse_block(inside_fn=inside_fn, requires_exit=False)

        # check for else
        nxt = self.peek_line()
        else_block = None
        if nxt is not None and len(nxt) == 1 and nxt[0].kind == "keyword" and nxt[0].text == "else":
            self.next_line()
            self.eat()  # "else"
            if self.peek() is not None:
                leftover = self.peek()
                raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after else")
            else_block = self.parse_block(inside_fn=inside_fn)

        return IfNode(if_tok.line, if_tok.col, cond, then_block, else_block)

    def parse_while(self, inside_fn=False):
        while_tok = self.eat()  # "while"
        cond = self.parse_expr()
        if self.peek() is not None:
            leftover = self.peek()
            raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after while condition")
        body = self.parse_block(inside_fn=inside_fn, requires_exit=False)
        return WhileNode(while_tok.line, while_tok.col, cond, body)

    def parse_arith(self):
        # arith ::= term { ("+" | "-") term }
        node = self.parse_term()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in ("+", "-"):
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_term())
        return node

    def parse_term(self):
        # term ::= factor { "*" factor }
        node = self.parse_operand()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text == "*":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_operand())
        return node

    def parse_expr(self, is_exit=False):
        # expr ::= arith [ ("==" | "!=") arith ]
        node = self.parse_arith()
        if (tok := self.peek()) is not None and tok.kind == "comparison":
            op_tok = self.eat()
            right = self.parse_arith()
            if (tok2 := self.peek()) is not None and tok2.kind == "comparison":
                raise_syntax_err(tok2.line, tok2.col, "multiple comparisons in one expression are not allowed")
            return BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, right)
        return node

    def parse_operand(self, is_exit=False):
        # operand ::= fn_call | ident | constant | "true" | "false"
        tok = self.peek()

        if tok is None:
            line, col = self.get_pos_info()
            if is_exit:
                raise_err(7, line, col)
            else:
                raise_syntax_err(line, col, "expected constant or variable, found end of line")

        if tok.kind == "operator" and tok.text == "!":
            bang = self.eat()
            operand = self.parse_operand(is_exit=is_exit)
            return NotNode(bang.line, bang.col, operand)
        elif tok.kind == "ident":
            # peek ahead: if next token is '(', it's a function call
            if self.pos + 1 < len(self.toks) and self.toks[self.pos + 1].kind == "lparen":
                return self.parse_fn_call()
            self.eat()
            return VarNode(tok.line, tok.col, tok.text)
        elif tok.kind == "constant":
            self.eat()
            return ConstNode(tok.line, tok.col, tok.text)
        elif tok.kind == "bool_literal":
            self.eat()
            return BoolNode(tok.line, tok.col, tok.text == "true")
        else:
            if is_exit:
                raise_err(7, tok.line, tok.col)
            else:
                raise_syntax_err(tok.line, tok.col, f"expected constant or variable, got '{tok.text}'")
    def parse_if(self):
        # if ::= "if" expr NL block [ "else" NL block ]
        if_tok = self.eat()  # 'if'
        condition = self.parse_expr()
        self.expect_eol()         # nothing after the condition on that line

        then_block = self.parse_block()

        # peek at the next line for an optional 'else'
        nxt = self.peek_line()
        else_block = None
        if nxt is not None and nxt[0].kind == "keyword" and nxt[0].text == "else":
            self.next_line()
            self.eat()            # consume 'else'
            self.expect_eol()     # nothing after 'else' on that line
            else_block = self.parse_block()

        return IfNode(if_tok.line, if_tok.col, condition, then_block, else_block)

    def parse_while(self):
        # while ::= "while" expr NL block
        while_tok = self.eat()  # 'while'
        condition = self.parse_expr()
        self.expect_eol()       # nothing after the condition on that line
        body_block = self.parse_block()
        return WhileNode(while_tok.line, while_tok.col, condition, body_block)

    def parse_block(self):
        # block ::= "{" NL { statement } [ exit NL ] "}" NL
        # The '{' must be on its own line (the line after 'if'/'else').
        nxt = self.peek_line()
        if nxt is None or nxt[0].kind != "lbrace":
            if nxt:
                raise_syntax_err(nxt[0].line, nxt[0].col, "expected '{'")
            else:
                raise_syntax_err(0, 0, "expected '{', found end of file")
        self.next_line()
        lbrace_tok = self.eat()   # '{'
        self.expect_eol()         # nothing after '{'

        stmts = []
        exit_node = None
        has_exit = False

        while True:
            nxt = self.peek_line()
            if nxt is None:
                raise_syntax_err(lbrace_tok.line, lbrace_tok.col,
                                 "block opened here is never closed")
            if nxt[0].kind == "rbrace":
                break

            self.next_line()
            tok = self.peek()

            if tok.kind == "statement" and tok.text == "exit":
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                exit_node = self.parse_exit()
                self.expect_eol()
                has_exit = True
            else:
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                stmt = self.parse_statement()
                stmts.append(stmt)
                if not isinstance(stmt, (IfNode, WhileNode)):
                    self.expect_eol()

        # consume the '}' line
        self.next_line()
        self.eat()                # '}'
        self.expect_eol()         # nothing after '}'

        if not stmts and exit_node is None:
            raise_syntax_err(lbrace_tok.line, lbrace_tok.col, "block must not be empty")

        return BlockNode(lbrace_tok.line, lbrace_tok.col, stmts, exit_node)

    def parse_fn_call(self):
        name_tok = self.eat()  # ident
        self.eat()             # '('
        args = []
        if self.peek() is not None and self.peek().kind != "rparen":
            args.append(self.parse_expr())
            while self.peek() is not None and self.peek().kind == "comma":
                self.eat()
                args.append(self.parse_expr())
        self.expect("rparen", "')'")
        return FnCallNode(name_tok.line, name_tok.col, name_tok.text, args)

    def parse_fn_call(self):
        name_tok = self.eat()  # ident
        self.eat()             # '('
        args = []
        if self.peek() is not None and self.peek().kind != "rparen":
            args.append(self.parse_expr())
            while self.peek() is not None and self.peek().kind == "comma":
                self.eat()
                args.append(self.parse_expr())
        self.expect("rparen", "')'")
        return FnCallNode(name_tok.line, name_tok.col, name_tok.text, args)


class SemanticChecker:
    def __init__(self):
        self.symbols = {}   # name -> DeclNode (top-level scope OR current fn scope)
        self.structs = {}   # name -> StructDefNode
        self.functions = {} # name -> FnDeclNode (for signature lookup)
        self.current_fn = None   # FnDeclNode being checked, or None (top-level)
        self.fn_locals = {}      # name -> DeclNode (current function locals + params)

    def lookup(self, node, name):
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]
        raise_err(2, node.line, node.col, ue_part=f"'{name}'")

    def _sem_err(self, line, col, msg):
        sys.stderr.write(f"compilation error: line {line}:{col}: {msg}\n")
        sys.exit(15)

    def _all_fields_mut(self, struct_name):
        if struct_name not in self.structs:
            return True
        sdef = self.structs[struct_name]
        for f in sdef.fields:
            if not f.mutable:
                return False
            if f.type_name in self.structs:
                if not self._all_fields_mut(f.type_name):
                    return False
        return True

    def _check_assignable(self, expr, want_type, at_node, what):
        """Verify expr.type can go into a variable of want_type."""
        have = expr.type
        if have == want_type:
            return
        if have == "i32" and want_type == "i64":
            return  # only widening allowed
        if isinstance(expr, ConstNode) and want_type in ("i32", "i64"):
            self._sem_err(expr.line, expr.col,
                          f"constant {expr.val} does not fit in {want_type}")
        self._sem_err(at_node.line, at_node.col,
                      f"cannot {what} of type {want_type} with a value of type {have}")

    def _validate_type(self, type_name, line, col):
        """Ensure type_name is a known built-in or struct."""
        if type_name not in ("i32", "i64", "bool") and type_name not in self.structs:
            raise_err(11, line, col, ue_part=f"'{type_name}'")

    # ── active symbol lookup ─────────────────────────────────────────
    def _lookup(self, name):
        """Return DeclNode for name; inside a function only fn_locals is visible."""
        if self.current_fn is not None:
            return self.fn_locals.get(name)
        return self.symbols.get(name)

    def _declare(self, name, decl_node):
        """Register a new local variable (raises if already declared)."""
        if self.current_fn is not None:
            if name in self.fn_locals:
                raise_err(1, decl_node.line, decl_node.col, ue_part=f"'{name}'")
            self.fn_locals[name] = decl_node
        else:
            if name in self.symbols:
                raise_err(1, decl_node.line, decl_node.col, ue_part=f"'{name}'")
            self.symbols[name] = decl_node

    # ── two-pass program visit ────────────────────────────────────────
    def visit_program(self, node):
        # Pass 1: collect struct defs and function signatures
        for stmt in node.stmts:
            if isinstance(stmt, StructDefNode):
                self.visit_struct_def(stmt)
            elif isinstance(stmt, FnDeclNode):
                self._register_fn_sig(stmt)

        # Pass 2: check non-struct/non-fn top-level stmts and fn bodies
        for stmt in node.stmts:
            if isinstance(stmt, StructDefNode):
                pass  # already done
            elif isinstance(stmt, FnDeclNode):
                self._check_fn_body(stmt)
            else:
                stmt.accept(self)

        if node.exit:
            node.exit.accept(self)

    def _register_fn_sig(self, node):
        """Register function name + signature without checking body."""
        if node.name in self.functions or node.name in self.structs or node.name in ("i32", "i64", "bool"):
            raise_err(1, node.line, node.col, ue_part=f"'{node.name}'")
        # Validate param and return types
        for p in node.params:
            self._validate_type(p.type_name, p.line, p.col)
        self._validate_type(node.ret_type, node.line, node.col)
        self.functions[node.name] = node

    def _check_fn_body(self, node):
        """Type-check the body of a function in its isolated scope."""
        saved_symbols = self.symbols
        saved_fn = self.current_fn
        saved_locals = self.fn_locals

        # Set up isolated scope: only params visible initially
        self.current_fn = node
        self.fn_locals = {}
        for p in node.params:
            # Create a pseudo-DeclNode for each parameter (immutable)
            pdecl = DeclNode(p.line, p.col, p.type_name, p.name, False, None)
            self.fn_locals[p.name] = pdecl

        # Check body block
        node.body.accept(self)

        # Validate exit type matches ret_type
        if node.body.exit_node is not None:
            exit_val = node.body.exit_node.val
            if exit_val.type not in ("i32", "i64", "bool") and exit_val.type not in self.structs:
                self._sem_err(node.body.exit_node.line, node.body.exit_node.col,
                              f"function '{node.name}' must return {node.ret_type}, got {exit_val.type}")
            try:
                self._check_assignable(exit_val, node.ret_type,
                                       node.body.exit_node,
                                       f"return from '{node.name}'")
            except SystemExit:
                raise

        # Restore
        self.current_fn = saved_fn
        self.fn_locals = saved_locals
        self.symbols = saved_symbols

    def visit_struct_def(self, node):
        if node.name in self.structs or node.name in ("i32", "i64", "bool"):
            raise_err(1, node.line, node.col, ue_part=f"'{node.name}'")
        for f in node.fields:
            if f.type_name == node.name:
                self._sem_err(f.line, f.col, f"struct '{node.name}' cannot contain itself")
            elif f.type_name not in ("i32", "i64", "bool") and f.type_name not in self.structs:
                raise_err(11, f.line, f.col, ue_part=f"'{f.type_name}'")
        self.structs[node.name] = node

    def visit_fn_decl(self, node):
        # Should only be called via _check_fn_body; fn signatures already registered
        pass

    def visit_decl(self, node):
        self._validate_type(node.type_name, node.line, node.col)

        if node.type_name in ("i32", "i64", "bool"):
            if len(node.inits) > 1:
                self._sem_err(node.line, node.col,
                              f"cannot initialise '{node.name}' of type {node.type_name} with multiple values")
            node.init.accept(self)  # resolve before the name enters scope
            self._check_assignable(node.init, node.type_name, node,
                                   f"initialise '{node.name}'")
            node.is_copy = False
        else:
            sdef = self.structs[node.type_name]
            if len(node.inits) == 1:
                init_expr = node.inits[0]
                init_type = init_expr.accept(self)
                if init_type == node.type_name:
                    node.is_copy = True
                elif len(sdef.fields) == 1:
                    self._check_assignable(init_expr, sdef.fields[0].type_name, node,
                                           f"initialise '{node.name}.{sdef.fields[0].name}'")
                    node.is_copy = False
                else:
                    self._sem_err(node.line, node.col,
                                  f"cannot initialise '{node.name}' of type {node.type_name}: expected {len(sdef.fields)} values, got 1")
            else:
                if len(node.inits) != len(sdef.fields):
                    self._sem_err(node.line, node.col,
                                  f"cannot initialise '{node.name}' of type {node.type_name}: expected {len(sdef.fields)} values, got {len(node.inits)}")
                for idx, (f, expr) in enumerate(zip(sdef.fields, node.inits)):
                    expr.accept(self)
                    self._check_assignable(expr, f.type_name, node,
                                           f"initialise '{node.name}.{f.name}'")
                node.is_copy = False

        self._declare(node.name, node)

    def visit_assign(self, node):
        decl = self._lookup(node.name)
        if decl is None:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")
        node.decl = decl
        if not decl.mutable:
            raise_err(12, node.line, node.col, ue_part=f"'{node.name}'")
        node.value.accept(self)

        if decl.type_name in self.structs:
            if not self._all_fields_mut(decl.type_name):
                self._sem_err(node.line, node.col,
                              f"cannot assign to '{node.name}': struct '{decl.type_name}' has immutable fields")

        self._check_assignable(node.value, decl.type_name, node,
                               f"assign to '{node.name}'")

    def visit_exit(self, node):
        node.val.accept(self)
        if node.val.type in self.structs:
            self._sem_err(node.line, node.col,
                          f"cannot exit with a value of type {node.val.type}")

    def visit_block(self, node):
        """Visit statements inside a block (if/while body; fn body is handled by _check_fn_body)."""
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit_node:
            node.exit_node.accept(self)
            # Validate return type if we are inside a function
            if self.current_fn is not None:
                self._check_assignable(node.exit_node.val, self.current_fn.ret_type,
                                       node.exit_node,
                                       f"return from '{self.current_fn.name}'")

    def visit_if(self, node):
        cond_type = node.cond.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"if condition must be bool, got {cond_type}")
        node.then_block.accept(self)
        if node.else_block:
            node.else_block.accept(self)

    def visit_while(self, node):
        cond_type = node.cond.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"while condition must be bool, got {cond_type}")
        node.body.accept(self)

    def visit_fn_call(self, node):
        if node.name not in self.functions:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")
        fn = self.functions[node.name]
        if len(node.args) != len(fn.params):
            self._sem_err(node.line, node.col,
                          f"function '{node.name}' expects {len(fn.params)} argument(s), got {len(node.args)}")
        for arg, param in zip(node.args, fn.params):
            arg.accept(self)
            self._check_assignable(arg, param.type_name, node,
                                   f"pass argument to '{param.name}'")
        node.type = fn.ret_type
        return node.type

    def visit_if(self, node):
        cond_type = node.condition.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"if condition must be bool, got {cond_type}")
        node.then_block.accept(self)
        if node.else_block:
            node.else_block.accept(self)

    def visit_while(self, node):
        cond_type = node.condition.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"while condition must be bool, got {cond_type}")
        node.body_block.accept(self)

    def visit_block(self, node):
        self.scopes.append({})
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)
        self.scopes.pop()

    def visit_not(self, node):
        t = node.operand.accept(self)
        if t != "bool":
            self._sem_err(node.line, node.col,
                          f"'!' requires bool operand, got {t}")
        node.type = "bool"
        return node.type

    def visit_if(self, node):
        cond_type = node.condition.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"if condition must be bool, got {cond_type}")
        node.then_block.accept(self)
        if node.else_block:
            node.else_block.accept(self)

    def visit_while(self, node):
        cond_type = node.condition.accept(self)
        if cond_type != "bool":
            self._sem_err(node.line, node.col,
                          f"while condition must be bool, got {cond_type}")
        node.body_block.accept(self)

    def visit_block(self, node):
        self.scopes.append({})
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)
        self.scopes.pop()

    def visit_not(self, node):
        t = node.operand.accept(self)
        if t != "bool":
            self._sem_err(node.line, node.col,
                          f"'!' requires bool operand, got {t}")
        node.type = "bool"
        return node.type

    def visit_binop(self, node):
        lt = node.left.accept(self)
        rt = node.right.accept(self)

        if node.op in ("+", "-", "*"):
            if lt == "bool":
                self._sem_err(node.line, node.col,
                              f"cannot apply '{node.op}' to bool")
            if rt == "bool":
                self._sem_err(node.line, node.col,
                              f"cannot apply '{node.op}' to bool")
            node.type = "i64" if (lt == "i64" or rt == "i64") else "i32"
        else:  # == or !=
            both_bool = (lt == "bool" and rt == "bool")
            both_int  = (lt in ("i32", "i64") and rt in ("i32", "i64"))
            if not (both_bool or both_int):
                self._sem_err(node.line, node.col,
                              f"cannot compare {lt} with {rt}")
            node.type = "bool"

        return node.type

    def visit_var(self, node):
        decl = self._lookup(node.name)
        if decl is None:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")
        node.decl = decl
        node.type = decl.type_name
        return node.type

    def visit_const(self, node):
        val = int(node.val)
        I32_MAX = 2**31 - 1
        I64_MAX = 2**63 - 1
        if val <= I32_MAX:
            node.type = "i32"
        elif val <= I64_MAX:
            node.type = "i64"
        else:
            self._sem_err(node.line, node.col,
                          f"constant {node.val} does not fit in i64")
        return node.type

    def visit_bool(self, node):
        node.type = "bool"
        return node.type


class CodeGenVisitor:
    def __init__(self, builder, printf_func, fmt_global):
        self.builder = builder
        self.printf = printf_func
        self.fmt_global = fmt_global
        # Symbol table: decl node -> alloca_ptr
        self.symbols = {}
        self.struct_defs = {}
        # function IR objects: fn_name -> ir.Function
        self.ir_functions = {}
        self.current_fn = None         # ir.Function currently being generated
        self.current_fn_node = None    # FnDeclNode currently being generated

    def _active_builder(self):
        return self.builder

    def visit_program(self, node):
        # Pass 1: declare all struct types and IR function prototypes
        for stmt in node.stmts:
            if isinstance(stmt, StructDefNode):
                stmt.accept(self)
            elif isinstance(stmt, FnDeclNode):
                self._declare_fn_ir(stmt)

        # Pass 2: generate function bodies, then top-level stmts
        for stmt in node.stmts:
            if isinstance(stmt, StructDefNode):
                pass
            elif isinstance(stmt, FnDeclNode):
                self._gen_fn_body(stmt)
            else:
                stmt.accept(self)

        if node.exit:
            node.exit.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.unreachable()

    def _declare_fn_ir(self, node):
        """Create an ir.Function prototype for the function (no body yet)."""
        param_types = [TYPES[p.type_name] for p in node.params]
        ret_llvm = TYPES[node.ret_type]
        fn_type = ir.FunctionType(ret_llvm, param_types)
        ir_fn = ir.Function(module, fn_type, name=f"f_{node.name}")
        self.ir_functions[node.name] = ir_fn

    def _gen_fn_body(self, node):
        """Generate LLVM IR for the function body."""
        ir_fn = self.ir_functions[node.name]

        # Save main context
        saved_builder = self.builder
        saved_symbols = self.symbols
        saved_fn = self.current_fn
        saved_fn_node = self.current_fn_node
        saved_param_ptrs = getattr(self, '_param_ptrs', {})

        # Create entry block and builder
        entry_bb = ir_fn.append_basic_block("entry")
        fn_builder = ir.IRBuilder(entry_bb)
        self.builder = fn_builder
        self.symbols = {}
        self._param_ptrs = {}
        self.current_fn = ir_fn
        self.current_fn_node = node

        # Allocate slots for parameters in the entry block
        for i, p in enumerate(node.params):
            llvm_type = TYPES[p.type_name]
            ptr = fn_builder.alloca(llvm_type, name=p.name)
            fn_builder.store(ir_fn.args[i], ptr)
            self._param_ptrs[p.name] = ptr

        # Generate body statements
        node.body.accept(self)

        # Restore
        self.builder = saved_builder
        self.symbols = saved_symbols
        self.current_fn = saved_fn
        self.current_fn_node = saved_fn_node
        self._param_ptrs = saved_param_ptrs


    def coerce(self, value, have, want):
        if have == "i32" and want == "i64":
            return self.builder.sext(value, I64, name="wide")
        return value

    def visit_struct_def(self, node):
        struct_type = module.context.get_identified_type(node.name)
        field_types = [TYPES[f.type_name] for f in node.fields]
        struct_type.set_body(*field_types)
        TYPES[node.name] = struct_type
        self.struct_defs[node.name] = node

    def alloca_in_entry(self, typ, name):
        entry_bb = self.builder.function.entry_basic_block
        curr_bb = self.builder.block
        if entry_bb.instructions:
            self.builder.position_before(entry_bb.instructions[0])
        else:
            self.builder.position_at_end(entry_bb)
        ptr = self.builder.alloca(typ, name=name)
        self.builder.position_at_end(curr_bb)
        return ptr

    def visit_fn_decl(self, node):
        pass  # handled by visit_program two-pass

    def visit_decl(self, node):
        llvm_type = TYPES[node.type_name]
        ptr = self.alloca_in_entry(llvm_type, node.name)
        self.symbols[node] = ptr

        if node.type_name in ("i32", "i64", "bool"):
            init_val = node.init.accept(self)
            init_val = self.coerce(init_val, node.init.type, node.type_name)
            self.builder.store(init_val, ptr)
        else:
            if getattr(node, "is_copy", False):
                val = node.init.accept(self)
                self.builder.store(val, ptr)
            else:
                sdef = self.struct_defs[node.type_name]
                for idx, (f, expr) in enumerate(zip(sdef.fields, node.inits)):
                    val = expr.accept(self)
                    val = self.coerce(val, expr.type, f.type_name)
                    field_ptr = self.builder.gep(ptr, [ir.Constant(I32, 0), ir.Constant(I32, idx)], name=f"{node.name}.{f.name}")
                    self.builder.store(val, field_ptr)

    def visit_assign(self, node):
        ptr = self.symbols[node.decl]
        val = node.value.accept(self)
        val = self.coerce(val, node.value.type, node.decl.type_name)
        self.builder.store(val, ptr)

    def visit_exit(self, node):
        val = node.val.accept(self)
        have = node.val.type
        if self.current_fn is not None:
            # Inside a function: emit ret
            val = self.coerce(val, have, self.current_fn_node.ret_type)
            self.builder.ret(val)
        else:
            # Top-level: print and ret 0
            if have == "bool":
                true_ptr = self.builder.gep(fmt_true, [ir.Constant(I32, 0), ir.Constant(I32, 0)])
                false_ptr = self.builder.gep(fmt_false, [ir.Constant(I32, 0), ir.Constant(I32, 0)])
                str_ptr = self.builder.select(val, true_ptr, false_ptr)
                fmt_ptr = self.builder.gep(fmt_bool, [ir.Constant(I32, 0), ir.Constant(I32, 0)])
                self.builder.call(self.printf, [fmt_ptr, str_ptr])
            else:
                val = self.coerce(val, have, "i64")
                fmt_ptr = self.builder.gep(self.fmt_global, [ir.Constant(I32, 0), ir.Constant(I32, 0)])
                self.builder.call(self.printf, [fmt_ptr, val])
            self.builder.ret(ir.Constant(I32, 0))

    def visit_not(self, node):
        val = node.operand.accept(self)
        # !bool: xor with 1 (i1)
        return self.builder.xor(val, ir.Constant(I1, 1), name="not")

    def visit_if(self, node):
        cond = node.condition.accept(self)

        then_bb  = self.builder.function.append_basic_block("then")
        else_bb  = self.builder.function.append_basic_block("else") if node.else_block else None
        merge_bb = self.builder.function.append_basic_block("merge")

        self.builder.cbranch(cond, then_bb, else_bb or merge_bb)

        # then arm
        self.builder.position_at_end(then_bb)
        node.then_block.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_bb)

        # else arm
        if node.else_block:
            self.builder.position_at_end(else_bb)
            node.else_block.accept(self)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)

        self.builder.position_at_end(merge_bb)

    def visit_while(self, node):
        cond_bb = self.builder.function.append_basic_block("while_cond")
        body_bb = self.builder.function.append_basic_block("while_body")
        end_bb  = self.builder.function.append_basic_block("while_end")

        self.builder.branch(cond_bb)

        # condition block
        self.builder.position_at_end(cond_bb)
        cond_val = node.condition.accept(self)
        self.builder.cbranch(cond_val, body_bb, end_bb)

        # body block
        self.builder.position_at_end(body_bb)
        node.body_block.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_bb)

        # end block
        self.builder.position_at_end(end_bb)

    def visit_block(self, node):
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)

    def visit_block(self, node):
        """Emit IR for statements and optional early-exit inside if/while blocks."""
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit_node:
            node.exit_node.accept(self)

    def visit_if(self, node):
        cond_val = node.cond.accept(self)
        fn_ir = self.current_fn if self.current_fn else self.builder.function
        then_bb = fn_ir.append_basic_block("then")
        merge_bb = fn_ir.append_basic_block("merge")

        if node.else_block:
            else_bb = fn_ir.append_basic_block("else")
            self.builder.cbranch(cond_val, then_bb, else_bb)
        else:
            self.builder.cbranch(cond_val, then_bb, merge_bb)

        # Then block
        self.builder.position_at_end(then_bb)
        node.then_block.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_bb)

        # Else block
        if node.else_block:
            self.builder.position_at_end(else_bb)
            node.else_block.accept(self)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)

        # Continue after if
        self.builder.position_at_end(merge_bb)


    def visit_while(self, node):
        fn_ir = self.current_fn if self.current_fn else self.builder.function
        cond_bb = fn_ir.append_basic_block("while_cond")
        body_bb = fn_ir.append_basic_block("while_body")
        end_bb  = fn_ir.append_basic_block("while_end")

        self.builder.branch(cond_bb)
        self.builder.position_at_end(cond_bb)
        cond_val = node.cond.accept(self)
        self.builder.cbranch(cond_val, body_bb, end_bb)

        self.builder.position_at_end(body_bb)
        node.body.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_bb)

        self.builder.position_at_end(end_bb)

    def visit_fn_call(self, node):
        ir_fn = self.ir_functions[node.name]
        fn_node = None
        # Find FnDeclNode to get param types for coercion
        # We stored them in checker.functions; access via node.type set by checker
        arg_vals = []
        for arg in node.args:
            v = arg.accept(self)
            arg_vals.append((v, arg.type))

        # Coerce args to param types
        fn_decl_node = None
        for stmt in ast.stmts:
            if isinstance(stmt, FnDeclNode) and stmt.name == node.name:
                fn_decl_node = stmt
                break
        coerced = []
        for (v, have), param in zip(arg_vals, fn_decl_node.params):
            coerced.append(self.coerce(v, have, param.type_name))

        return self.builder.call(ir_fn, coerced)

    def visit_binop(self, node):
        left_val = node.left.accept(self)
        right_val = node.right.accept(self)
        
        have_l = node.left.type
        have_r = node.right.type

        if node.op in ("==", "!="):
            target = "i64" if (have_l == "i64" or have_r == "i64") else have_l
            if have_l == "bool": target = "bool"
            
            left_val = self.coerce(left_val, have_l, target)
            right_val = self.coerce(right_val, have_r, target)
            cmp = self.builder.icmp_signed(node.op, left_val, right_val)
            return cmp  # I1

        # arithmetic
        target = node.type
        left_val = self.coerce(left_val, have_l, target)
        right_val = self.coerce(right_val, have_r, target)

        if node.op == "+":
            return self.builder.add(left_val, right_val)
        elif node.op == "-":
            return self.builder.sub(left_val, right_val)
        elif node.op == "*":
            return self.builder.mul(left_val, right_val)

    def visit_var(self, node):
        # First check if it's a function parameter slot
        if self.current_fn is not None and hasattr(self, '_param_ptrs') and node.name in self._param_ptrs:
            return self.builder.load(self._param_ptrs[node.name], name=node.name)
        ptr = self.symbols[node.decl]
        return self.builder.load(ptr, name=node.name)

    def visit_const(self, node):
        llvm_t = TYPES[node.type]
        return ir.Constant(llvm_t, int(node.val))

    def visit_bool(self, node):
        return ir.Constant(I1, 1 if node.val else 0)


try:
    with open(args.source_path, "rb") as f:
        file_bytes = f.read()
except FileNotFoundError:
    sys.stderr.write(f"error: file not found: {args.source_path}\n")
    sys.exit(1)

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

checker = SemanticChecker()
ast.accept(checker)

codegen = CodeGenVisitor(builder, printf, fmt)
ast.accept(codegen)

if args.output_path:
    with open(args.output_path, "w") as out_f:
        out_f.write(str(module))
