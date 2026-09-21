# Compiler

## Requirements

* Python 3.10+
* `llvmlite`
* LLVM Toolchain (`llc`, `clang`) — only needed to actually run a compiled program (step 2 below); the automated test suite does not require them.

---

## Project Structure

```text
.
├── compiler.py              # Main compiler script (hand-written byte-level lexer + llvmlite codegen)
└── tests/                   # Test suite folder
    ├── run_tests.sh         # Automated test suite runner
    ├── valid_*.txt / .out   # Positive test cases and their expected token stream
    └── invalid_*.txt / .err # Negative test cases and their expected stderr message
```

---

## Usage

### 1. Compile Source Code to LLVM IR

```bash
python3 compiler.py <source_path.txt> <output_path.ll>
```

**Example:**

```bash
python3 compiler.py input.txt output.ll
```

### 2. Build and Execute the Output

```bash
llc -filetype=obj -relocation-model=pic output.ll -o output.o
clang -fPIE output.o -o program
./program
```

---

## Expected Behavior & Error Handling

* **Successful Compilation:**
  * Generates a valid `.ll` IR file.
  * Executing the compiled binary prints:
    ```text
    Program exit with result <value>
    ```
  * Exits with code `0`.

* **Compilation Error:**
  * Outputs a single line to `sys.stderr` in the format:
    ```text
    compilation error: line <line>:<col> <error_message>
    ```
    `line:col` is the 1-based position of the first byte of the offending token.
  * Exits with a non-zero code equal to the error number below.
  * **No `.ll` file is written** — the output file is only created after the whole program has compiled without errors.

### Error Codes and Messages Mapping

| Error Code | Standard Error Message (`sys.stderr`) | Trigger Condition |
| --- | --- | --- |
| **1** | `redeclared variable` | A variable name is declared a second time |
| **2** | `undeclared variable` | A variable is read (in an expression, assignment, or `exit`) before it was declared |
| **4** | `unparsable statement` | A line is not a valid declaration / assignment / `exit`, has the wrong number of tokens, or an initializer/assignment expression is empty or malformed |
| **5** | `missing exit statement` | The source file ends without a terminal `exit` statement |
| **6** | `exit must be the last statement` | A statement follows `exit` |
| **7** | `unparsable exit statement` | `exit` has no argument |
| **8** | `unsupported operator` | The operator token in an expression is not one the code generator knows how to build |
| **9** | `'{' is not closed before the end of the line` | A line ends (`\n`) while an initializer block opened with `{` has no matching `}` |
| **10** | `unexpected byte <byte>` | A byte doesn't fit any lexer state: an unknown character, a letter following a number, or `:` not immediately followed by `=` |
| **11** | `unknown type <name>` | A declaration uses a type name that is not registered in `TYPES` |
| **12** | `cannot assign to immutable variable <name>` | A variable not declared `mut` is the target of a `:=` assignment |

> **Note:** Code **3** (`invalid variable name`) is defined but not currently raised anywhere in `compiler.py`.
> Codes **8** and **11** are also effectively unreachable with the current lexer/type table: any operator
> character other than `+ - *` (e.g. `/`, `%`) fails lexing as an *unexpected byte* (code **10**) before an
> expression is ever evaluated, and `TYPES`/`KEYWORDS` currently only register `i32`, so any other word is
> lexed as `ident` rather than `typename` and never reaches the type check.

---

## Automated Test Suite

To verify all test cases (both positive compilation tests and expected syntax/semantic failure tests), run:

```bash
chmod +x tests/run_tests.sh
./tests/run_tests.sh
```

**Test Verification Logic:**

* **`valid_*.txt`:** Runs `compiler.py` and confirms it exits with code `0`, then re-runs it as a Python module to
  pull out the lexer's token stream and compares each token, rendered with the project's own `Token.to_str()`,
  against the matching `valid_*.out` reference file.
* **`invalid_*.txt`:** Runs `compiler.py` and confirms it exits with a non-zero code, then compares the exact text
  written to `stderr` against the matching `invalid_*.err` reference file.

The runner does not invoke `llc`/`clang` or execute a compiled binary — it exercises the lexer and the compiler's
error-reporting directly, which is enough to catch regressions in tokenization, line:col tracking, and error
messages without needing the LLVM toolchain installed.