from llvmlite import ir
import llvmlite.binding as llvm
import argparse
import sys
import re

parser = argparse.ArgumentParser()
parser.add_argument("source_path", help="path to the .txt file with your code")
parser.add_argument("output_path", help="path to the .ll file, where compiler will place the intermediate code")

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

symbols = {}
RESERVED = {"int", "exit"}
VAR_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

def raise_err(error_number, line_number):
    ERRORS = {
        1: "redeclared variable",
        2: "undeclared variable",
        3: "invalid variable name",
        4: "unparsable statement",
        5: "missing exit statement",
        6: "exit must be the last statement",
        7: "unparsable exit statement",
        8: "unsupported operator",
    }

    msg = ERRORS.get(error_number, "unknown compilation error")

    sys.stderr.write(f"compilation error: line {line_number}: {msg}\n")
    sys.exit(1)

def is_valid_var_name(name):
    return bool(VAR_PATTERN.match(name)) and name not in RESERVED

def get_value(operand_str, l_num):
    operand_str = operand_str.strip()

    if operand_str.isdigit() or (operand_str.startswith("-") and operand_str[1:].isdigit()):
        return ir.Constant(I32, int(operand_str))
    elif operand_str in symbols:
        return builder.load(symbols[operand_str])
    elif is_valid_var_name(operand_str):
        raise_err(2, l_num)
    else:
        raise_err(4, l_num)

def is_number(s):
    s = s.strip()
    return s.isdigit() or (s.startswith("-") and s[1:].isdigit())

has_exit = False
last_line_num = 0

with open(args.source_path, "r") as input_f:
    for l_num, raw_line in enumerate(input_f, 1):
        last_line_num = l_num
        line = raw_line.strip()

        if has_exit:
            raise_err(6, l_num)

        if line.startswith("int "):
            parts = line.split()
            if len(parts) != 2:
                raise_err(4, l_num)

            variable = parts[1]
            if not is_valid_var_name(variable):
                raise_err(3, l_num)
            if variable in symbols:
                raise_err(1, l_num)

            symbols[variable] = builder.alloca(I32, name=variable)

        elif line.startswith("exit ") or line == "exit":
            parts = line.split()
            if len(parts) != 2 or parts[0] != "exit":
                raise_err(7, l_num)

            variable = parts[1]
            if not is_valid_var_name(variable):
                raise_err(7, l_num)
            if variable not in symbols:
                raise_err(2, l_num)

            builder.call(
                printf,
                [
                    builder.bitcast(fmt, ir.PointerType(I8)),
                    builder.load(symbols[variable]),
                ],
            )
            builder.ret(ir.Constant(I32, 0))
            has_exit = True

        elif ":=" in line:
            for unsupp in ["/", "%", "^", "&", "|"]:
                if unsupp in line:
                    raise_err(8, l_num)

            parts = line.split(":=")
            if len(parts) != 2:
                raise_err(4, l_num)

            var = parts[0].strip()
            expr = parts[1].strip()

            if not is_valid_var_name(var):
                raise_err(3, l_num)
            if var not in symbols:
                raise_err(2, l_num)

            if is_number(expr) or (
                    is_valid_var_name(expr) or expr in symbols
            ):
                val = get_value(expr, l_num)
                builder.store(val, symbols[var])
            else:

                match = re.match(r"^(.+?)([+*-])(.+)$", expr)
                if not match:
                    raise_err(4, l_num)

                left_str = match.group(1).strip()
                op = match.group(2)
                right_str = match.group(3).strip()

                left_val = get_value(left_str, l_num)
                right_val = get_value(right_str, l_num)

                if op == "+":
                    res = builder.add(left_val, right_val)
                elif op == "-":
                    res = builder.sub(left_val, right_val)
                elif op == "*":
                    res = builder.mul(left_val, right_val)

                builder.store(res, symbols[var])

        else:
            raise_err(4, l_num)

if not has_exit:
    raise_err(5, max(last_line_num, 1))

with open(args.output_path, "w") as out_f:
    out_f.write(str(module))


