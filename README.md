# Compiler

## Requirements

* Python 3.10+
* `llvmlite`
* LLVM Toolchain (`llc`, `clang`) — only needed to actually run a compiled program (step 2 below).
  The automated test suite does **not** require them: it uses `lli` when available and otherwise
  falls back to executing the IR in-process via `llvmlite`'s own JIT (see `tests/run_ll.py`).

---

## Project Structure

```text
.
├── compiler.py                # Lexer → recursive-descent parser → AST → llvmlite codegen
├── grammar.ebnf                # EBNF grammar of the language (Task 1)
└── tests/
    ├── run_tests.sh            # Automated test suite runner
    ├── run_ll.py                # llvmlite-JIT fallback used when `lli` isn't on PATH
    ├── valid_*.txt              # Programs that must compile and run
    ├── valid_*.out               # Their expected runtime output ("Program exit with result N")
    ├── valid_*.ast                # Expected `--ast` dump
    ├── valid_*.tokens              # Expected `--tokens` dump
    ├── invalid_*.txt              # Programs that must fail to compile
    ├── invalid_*.err                # Expected stderr message
    └── invalid_*.ast                # For a few tests: the program is syntactically valid but
                                       # semantically wrong, so `--ast` is expected to *succeed*
                                       # and match this tree even though full compilation fails
```

> `grammar.ebnf` is the Task 1 deliverable — make sure it's committed at the repo root.

---

## Usage

### 1. Compile source code to LLVM IR

```bash
python3 compiler.py <source_path.txt> <output_path.ll>
```

**Example:**

```bash
python3 compiler.py input.txt output.ll
```

### 2. Inspect the compiler's intermediate stages

`output_path` is optional — leave it off to check a program without writing anything:

```bash
python3 compiler.py input.txt --tokens   # print the lexer's token stream, nothing else
python3 compiler.py input.txt --ast      # print the AST and exit (no codegen, no file written)
```

`--ast` only runs the parser — it stops **before** the code-generation walk, so it reports syntax
errors but not semantic ones (see the note under the error table).

### 3. Build and execute the output

```bash
llc -filetype=obj -relocation-model=pic output.ll -o output.o
clang -fPIE output.o -o program
./program
```

While debugging, `lli output.ll` runs the IR directly without the `llc`/`clang` steps.

---

## Expected Behavior & Error Handling

* **Successful compilation:**
  * Generates a valid `.ll` IR file (only if `output_path` was given).
  * Executing the compiled program prints:
    ```text
    Program exit with result <value>
    ```
  * Exits with code `0`.

* **Compilation error:**
  * Outputs a single line to `sys.stderr` in the format:
    ```text
    compilation error: line <line>:<col>: <error_message>
    ```
    `line:col` is the 1-based position of the token that caused the error. For an error where the
    line ended too early (e.g. `x := x +`), the position is the column right after the last token
    of that line.
  * Exits with a non-zero code.
  * **No `.ll` file is written** — the output file is only created after the whole program has
    compiled without errors.

Errors come from two independent places in `compiler.py`, with two independent codes:

* **`raise_err(code, ...)`** — lexer errors and semantic errors caught during the code-generation
  walk (`CodeGenVisitor`). Each has its own fixed exit code, from the table below.
* **`raise_syntax_err(line, col, msg)`** — every grammar/syntax error raised by the parser (`Parser`
  class: `expect()`, `parse_statement()`, `parse_operand()`, the "leftover tokens" check, …). All of
  these exit with code **13** and carry a free-form message rather than one looked up from a table.

### Error Codes and Messages Mapping

| Error Code | Message | Raised by | Trigger Condition |
| --- | --- | --- | --- |
| **1** | `redeclared variable 'name'` | codegen (`visit_decl`) | A variable name is declared a second time |
| **2** | `undeclared variable 'name'` | codegen (`visit_assign`, `visit_var`) | A variable is read or assigned before it was declared |
| **5** | `missing exit statement` | codegen (`visit_program`) | The program has no `exit` statement |
| **6** | `exit must be the last statement` | parser (`parse_program`) | A statement follows `exit` |
| **7** | `unparsable exit statement` | parser (`parse_exit`) | `exit` has no argument, or extra tokens follow the exit value |
| **9** | `'{' is not closed before the end of the line` | lexer | A line ends while an initializer block opened with `{` has no matching `}` |
| **10** | `unexpected byte <byte>` | lexer | A byte doesn't fit any lexer state: an unknown character, a letter after a digit, or `:` not immediately followed by `=` |
| **12** | `cannot assign to immutable variable 'name'` | codegen (`visit_assign`) | A variable not declared `mut` is the target of `:=` |
| **13** | *(free-form, e.g. `expected ':=', got '5'`)* | parser (`raise_syntax_err`) | Any grammar violation: a statement that doesn't start with `i32`/an identifier/`exit`, a missing `{`/`}`/`:=`, two operators in a row, an operator at the end of a line, tokens left over after a complete statement, a missing variable name, … |

> **Codes 3, 4, 8, 11** (`invalid variable name`, `unparsable statement`, `unsupported operator`,
> `unknown type`) are defined in the `ERRORS` table inside `raise_err` but are not reachable with the
> current grammar and lexer:
> * what used to be code 4 (`unparsable statement`) in the token-only checker is now entirely
>   superseded by the parser's own **code 13** syntax errors.
> * code 8 is dead because `BinOpNode.op` can only ever be `+`, `-` or `*` — the only operators the
>   parser ever builds a node for.
> * code 11 is dead because `TYPES`/`KEYWORDS` only register `i32`; any other word lexes as `ident`
>   and is rejected by the parser as "cannot start a statement with …" (code 13) rather than reaching
>   the type check.
> * code 3 is simply never raised anywhere.

**Semantic checks live in codegen, not in the parser.** Redeclaration (1), use-before-declaration
(2), assignment to a `const` (12), and a missing `exit` (5) are only checked while walking the AST to
generate IR — `ast.accept(codegen)` — which runs *after* the `--ast` early exit. That means a program
can be **syntactically valid** (parses and dumps a correct AST under `--ast`) while still being
**semantically invalid** (fails a full compile). `tests/invalid_3_assign_const`,
`invalid_4_use_before_decl`, `invalid_7_redeclaration_and_extra_tokens` and `invalid_16_missing_exit`
are built specifically to demonstrate this: each has both an `.err` (the full compile fails) and an
`.ast` (yet `--ast` succeeds and matches it).

---

## Automated Test Suite

```bash
chmod +x tests/run_tests.sh
./tests/run_tests.sh
```

**Test verification logic:**

* **`valid_*.txt`:**
  1. `compiler.py` must exit `0` and produce a `.ll` file.
  2. Executing that IR (`lli`, or the bundled `run_ll.py` JIT fallback if `lli` isn't installed) must
     print exactly what `valid_*.out` says.
  3. `compiler.py --tokens` must match `valid_*.tokens` (checked when that file exists).
  4. `compiler.py --ast` must match `valid_*.ast` (checked when that file exists).

* **`invalid_*.txt`:**
  1. `compiler.py` must exit non-zero.
  2. Its `stderr` must match `invalid_*.err` exactly.
  3. No `.ll` file may be produced.
  4. If a matching `invalid_*.ast` file exists, `--ast` is checked too and is **expected to
     succeed** — see the semantic-vs-syntax note above.

The runner reports `PASS`/`FAIL`/`SKIP` per test and a final tally, and exits non-zero if anything
failed (safe to wire into CI).