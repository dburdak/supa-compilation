from llvmlite import ir
import llvmlite.binding as llvm
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("source_path", help="path to the .txt file with your code")
parser.add_argument("output_path", help="path to the .ll file, where compiler will place the intermediate code")
parser.add_argument("--tokens", action="store_true",
                    help="print the token stream to stdout")

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
        return f"({self.kind}, {self.text}, {self.line}, {self.col})\n"


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


with open(args.source_path, "rb") as f:
    file_bytes = f.read()

lines = lex(file_bytes)



symbols = {} # "name" : ["IR_ptr", bool(mut or not)]
# REWRITE
def get_value(token: Token):
    if token.kind == "constant":
        return ir.Constant(I32, int(token.text))
    elif token.kind == "ident":
        if token.text not in symbols:
            raise_err(2, token.line, token.col)# undeclared variable
        ptr = symbols[token.text][0]
        return builder.load(ptr)
    else:
        raise_err(4, token.line, token.col)


def eval(expr_tokens):
    if not expr_tokens:
        raise_err(4, 0, 0)

    if len(expr_tokens) == 1:
        return get_value(expr_tokens[0])

    elif len(expr_tokens) == 3:
        left_tok, op_tok, right_tok = expr_tokens
        if op_tok.text not in OPERATORS:
            raise_err(8, op_tok.line, op_tok.col) # unsupported operator

        left_val = get_value(left_tok)
        right_val = get_value(right_tok)
        build_op = OPERATORS[op_tok.text]
        return build_op(left_val, right_val)

    else:
        raise_err(4, expr_tokens[0].line, expr_tokens[0].col)


def handle_typename(l_state):
    type_tok = l_state[0]# first token
    if type_tok.text not in TYPES:
        raise_err(11, type_tok.line, type_tok.col, ue_part=type_tok.text)

    is_mut = False
    idx = 1

    if idx < len(l_state) and l_state[idx].kind == "specifier" and l_state[idx].text == "mut":
        is_mut = True
        idx += 1

    if idx >= len(l_state) or l_state[idx].kind != "ident":
        raise_err(4, type_tok.line, type_tok.col)

    var_tok = l_state[idx]
    if var_tok.text in symbols:
        raise_err(1, var_tok.line, var_tok.col) # redeclared variable

    idx += 1

    if idx >= len(l_state) or l_state[idx].kind != "lbrace" or l_state[-1].kind != "rbrace":
        raise_err(4, var_tok.line, var_tok.col)

    expr_tokens = l_state[idx + 1: -1]
    init_val = eval(expr_tokens)

    alloca_ptr = builder.alloca(TYPES[type_tok.text], name=var_tok.text)
    builder.store(init_val, alloca_ptr)
    symbols[var_tok.text] = (alloca_ptr, is_mut)



def handle_ident(line):
    var_tok = line[0]
    if var_tok.text not in symbols:
        raise_err(2, var_tok.line, var_tok.col) # undeclared variable

    alloca_ptr, is_mut = symbols[var_tok.text]
    if not is_mut:
        raise_err(12, var_tok.line, var_tok.col, ue_part = var_tok.text)

    if len(line) < 3 or line[1].kind != "assignment":
        raise_err(4, var_tok.line, var_tok.col)

    expr_tokens = line[2:]
    val = eval(expr_tokens)
    builder.store(val, alloca_ptr)


def handle_statement(line):
    global has_exit
    stmt_tok = line[0]

    if stmt_tok.text != "exit":
        raise_err(4, stmt_tok.line, stmt_tok.col)

    if len(line) < 2:
        raise_err(7, stmt_tok.line, stmt_tok.col) # unparsable exit statement

    expr_tokens = line[1:]
    val = eval(expr_tokens)

    fmt_ptr = builder.bitcast(fmt, ir.PointerType(I8))
    builder.call(printf, [fmt_ptr, val])
    builder.ret(ir.Constant(I32, 0))
    has_exit = True

has_exit = False
last_line_num = 1


for line in lines:
    if not line:
        continue

    first_token = line[0]
    last_line_num = first_token.line

    if has_exit:
        raise_err(6, first_token.line, first_token.col)

    if first_token.kind == "typename": handle_typename(line)
    elif first_token.kind == "ident": handle_ident(line)
    elif first_token.kind == "statement": handle_statement(line)
    else:
        raise_err(4, first_token.line, first_token.col) # unparsable statement

if not has_exit:
    raise_err(5, last_line_num, 1)

with open(args.output_path, "w") as out_f:
    out_f.write(str(module))

    
if args.tokens:
    for line in lexer_lines:
        for token in line:
            token.print()
            print(" ")
        print("\n")

