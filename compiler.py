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
        14: "expected '!=' (a single '!' is not an operator)",
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
    while i <= len(data):
        b = data[i] if i < len(data) else None

        if state == "START":
            if b is None:
                break
            elif b in (32, 9):
                pass
            elif b == 10:
                if open_brace_col is not None:
                    if len(tokens) == 1 and tokens[0].kind == "lbrace":
                        open_brace_col = None
                    else:
                        raise_err(9, line, open_brace_col)
                lexer_lines.append(tokens)
                tokens = []
                line += 1; col = 0
            elif is_alpha(b):
                state, start, start_col = "IDENT", i, col
            elif is_digit(b):
                state, start, start_col = "NUMBER", i, col
            elif b == ord("{"):
                tokens.append(Token("lbrace", "{", line, col))
                open_brace_col = col
            elif b == ord("}"):
                tokens.append(Token("rbrace", "}", line, col))
                open_brace_col = None
            elif b == ord(","):
                tokens.append(Token("comma", ",", line, col))
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
            elif b is None:
                raise_err(14, line, start_col)
            else:
                raise_err(14, line, start_col)

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


class ExitNode(Node):
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
        self.line_idx = 0

    def peek_line(self):
        idx = self.line_idx
        while idx < len(self.lines) and not self.lines[idx]:
            idx += 1
        return self.lines[idx] if idx < len(self.lines) else None

    def next_line(self):
        while self.line_idx < len(self.lines) and not self.lines[self.line_idx]:
            self.line_idx += 1
        if self.line_idx < len(self.lines):
            self.toks = self.lines[self.line_idx]
            self.pos = 0
            self.line_idx += 1
            return self.toks
        self.toks = []
        self.pos = 0
        return None

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

        while self.peek_line() is not None:
            if has_exit:
                nxt = self.peek_line()
                raise_err(6, nxt[0].line, nxt[0].col)

            self.next_line()
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
                    raise_err(7, line, col)
                else:
                    leftover = self.peek()
                    raise_syntax_err(leftover.line, leftover.col, f"unexpected '{leftover.text}' after statement")

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
            raise_syntax_err(line, col, "expected statement, found end of line")

        if tok.kind == "keyword" and tok.text == "struct":
            return self.parse_struct_def()
        elif tok.kind == "typename":
            return self.parse_decl()
        elif tok.kind == "ident":
            # Disambiguate between struct object declaration and assignment:
            # Declaration: StructName [mut] var{...}
            if self.pos + 1 < len(self.toks):
                next_tok = self.toks[self.pos + 1]
                if next_tok.kind == "specifier" and next_tok.text == "mut":
                    return self.parse_decl()
                if next_tok.kind == "ident":
                    return self.parse_decl()
            return self.parse_assignment()
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
        val = self.parse_operand(is_exit=True)
        return ExitNode(exit_tok.line, exit_tok.col, val)

    def parse_arith(self):
        # arith ::= term { ("+" | "-") term }
        node = self.parse_term()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "+-":
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

    def parse_expr(self):
        # expr ::= arith [ ("==" | "!=") arith ]
        node = self.parse_arith()
        if (tok := self.peek()) is not None and tok.kind == "comparison":
            op_tok = self.eat()
            right = self.parse_arith()
            # only one comparison per expression is allowed
            if (tok2 := self.peek()) is not None and tok2.kind == "comparison":
                raise_syntax_err(tok2.line, tok2.col, "multiple comparisons in one expression are not allowed")
            return BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, right)
        return node

    def parse_operand(self, is_exit=False):
        # operand ::= ident | constant | "true" | "false"
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
        elif tok.kind == "bool_literal":
            self.eat()
            return BoolNode(tok.line, tok.col, tok.text == "true")
        else:
            if is_exit:
                raise_err(7, tok.line, tok.col)
            else:
                raise_syntax_err(tok.line, tok.col, f"expected constant or variable, got '{tok.text}'")


class SemanticChecker:
    def __init__(self):
        self.symbols = {}  # name -> DeclNode
        self.structs = {}  # name -> StructDefNode

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
        # constant that is too large for the declared integer type
        if isinstance(expr, ConstNode) and want_type in ("i32", "i64"):
            self._sem_err(expr.line, expr.col,
                          f"constant {expr.val} does not fit in {want_type}")
        self._sem_err(at_node.line, at_node.col,
                      f"cannot {what} of type {want_type} with a value of type {have}")


    def visit_program(self, node):
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)

    def visit_struct_def(self, node):
        if node.name in self.structs or node.name in ("i32", "i64", "bool"):
            raise_err(1, node.line, node.col, ue_part=f"'{node.name}'")
        for f in node.fields:
            if f.type_name == node.name:
                self._sem_err(f.line, f.col, f"struct '{node.name}' cannot contain itself")
            elif f.type_name not in ("i32", "i64", "bool") and f.type_name not in self.structs:
                raise_err(11, f.line, f.col, ue_part=f"'{f.type_name}'")
        self.structs[node.name] = node

    def visit_decl(self, node):
        if node.name in self.symbols:
            raise_err(1, node.line, node.col, ue_part=f"'{node.name}'")
        if node.type_name not in ("i32", "i64", "bool") and node.type_name not in self.structs:
            raise_err(11, node.line, node.col, ue_part=f"'{node.type_name}'")

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

        self.symbols[node.name] = node

    def visit_assign(self, node):
        if node.name not in self.symbols:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")
        decl = self.symbols[node.name]
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

    def visit_binop(self, node):
        lt = node.left.accept(self)
        rt = node.right.accept(self)

        if node.op in ("+", "-", "*"):
            # arithmetic: both must be integers
            if lt == "bool":
                self._sem_err(node.line, node.col,
                              f"cannot apply '{node.op}' to bool")
            if rt == "bool":
                self._sem_err(node.line, node.col,
                              f"cannot apply '{node.op}' to bool")
            # result is the wider type
            node.type = "i64" if (lt == "i64" or rt == "i64") else "i32"
        else:  # == or !=
            # both must be integers (any mix) or both bools
            both_bool = (lt == "bool" and rt == "bool")
            both_int  = (lt in ("i32", "i64") and rt in ("i32", "i64"))
            if not (both_bool or both_int):
                self._sem_err(node.line, node.col,
                              f"cannot compare {lt} with {rt}")
            node.type = "bool"

        return node.type

    def visit_var(self, node):
        if node.name not in self.symbols:
            raise_err(2, node.line, node.col, ue_part=f"'{node.name}'")
        node.decl = self.symbols[node.name]
        node.type = node.decl.type_name
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

    def visit_program(self, node):
        for stmt in node.stmts:
            stmt.accept(self)
        if node.exit:
            node.exit.accept(self)

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

    def visit_decl(self, node):
        llvm_type = TYPES[node.type_name]
        ptr = self.builder.alloca(llvm_type, name=node.name)
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
