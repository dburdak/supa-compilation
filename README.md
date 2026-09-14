# Compiler

## Requirements

* Python 3.10+
* `llvmlite`
* LLVM Toolchain (`llc`, `clang`)

---

## Project Structure

```text
.
├── compiler.py             # Main compiler script
└── tests/                  # Test suite folder
    ├── run_tests.sh        # Automated test suite runner
    ├── pass_*.txt / .out   # Positive test cases and expected outputs
    └── fail_*.txt / .err   # Negative test cases and expected stderr errors

```
___

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
llc -filetype=obj output.ll -o output.o
clang output.o -o program
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
* Outputs an error message to `sys.stderr` in the following format:
```text
compilation error: line N: <error_message>

```


* Exits with a non-zero code.
* **Suppresses file generation** (no `.ll` file is created).



### Error Codes and Messages Mapping

| Error Code | Standard Error Message (`sys.stderr`) | Trigger Condition |
| --- | --- | --- |
| **1** | `redeclared variable` | Variable is declared more than once |
| **2** | `undeclared variable` | Variable used without prior declaration |
| **3** | `invalid variable name` | Variable name breaks syntax rules or uses reserved words |
| **4** | `unparsable statement` | General syntax error or empty statement |
| **5** | `missing exit statement` | Source file ends without a terminal `exit` statement |
| **6** | `exit must be the last statement` | Statements exist after the `exit` command |
| **7** | `unparsable exit statement` | Invalid argument format in `exit` statement |
| **8** | `unsupported operator` | Statement uses prohibited operators (e.g., `/`, `%`) |

---

## Automated Test Suite

To verify all test cases (both positive compilation tests and expected syntax/semantic failure tests), run:

```bash
chmod +x tests/run_tests.sh
./tests/run_tests.sh
```

**Test Verification Logic:**

* **`pass_*.txt`:** Confirms valid LLVM IR emission, object compilation via `llc`/`clang`, and matches the program's stdout against the corresponding `.out` reference file.
* **`fail_*.txt`:** Verifies that a compilation error is caught, the exact message matches the `.err` reference file in `stderr`, and output file creation is safely aborted.
