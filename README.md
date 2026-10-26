# Supa Compiler

A custom educational compiler for the "Supa" programming language, written in Python with `llvmlite`.

## Practice 6 Features (Structs & Functions)

This version adds full support for user-defined structs, functions, recursion, and field access chains:
- **Struct Definitions & Objects**:
  - `struct` declaration with typed fields (`i32`, `i64`, `bool` or another struct).
  - Field mutability: fields are constant unless declared with `mut`.
  - Object initialisation with mandatory curly braces `{...}` matching field types or nested braces `{{...}, ...}`.
  - Object copying (`Point q{p}`).
  - Full-struct assignment (`:=`) only permitted if all fields at every depth are `mut`.
- **Functions & Recursion**:
  - `fn name := (params) -> ReturnType { ... exit result }` syntax.
  - Parameters are passed by value (copies) and immutable inside the function body.
  - Function body is an isolated scope (cannot access top-level variables).
  - Recursion supported (e.g. `fib`).
  - Prefixing of function names in LLVM IR (e.g. `f_...`) to prevent clashing with runtime symbols.
- **Fixed Program Structure**:
  - Program structure strictly ordered: all `struct` definitions first, followed by all `fn` declarations, followed by top-level statements, ending with `exit`.
- **Field Access Chains**:
  - Accessing fields via dot syntax (`p.x`, `c.center.radius`) in expressions.
  - Assigning to field access chains (`c.center.x := 20`) requiring mutability along the entire path.
- **LLVM IR Code Generation**:
  - Named identified struct types in LLVM IR context (`%"Point" = type { i32, i32 }`).
  - Access to fields via GEP indices computed during semantic analysis.

## Practice 8 Features (Callable Objects)

A struct with a member function named `call` can be invoked like a function (`triple(14)`), with the semantic
pass rewriting the call to the existing member-call representation. This also works for callable struct fields
(`shape.scale(7)`). Mutable `call` methods follow the same mutability rules as other member functions.

Lambda statements capture visible variables by value into compiler-generated closure structs. Captures are
constant inside the lambda unless declared `mut`; a mutable capture makes the closure's `call` method mutating.
Closure calls use the same callable-object semantics as structs with a `call` member function. Use
`--ast-checked` to inspect the AST after semantic lowering.

## Requirements

- Python 3.x
- `llvmlite`

Note: Native LLVM command-line tools like `llc` or `clang` are **not** required for the autotests. The test runner uses `lli` if available on your `PATH`. If not, it falls back to `tests/run_ll.py` which uses the `llvmlite` JIT compiler to execute the generated IR directly.

## Project Structure

```text
.
├── compiler.py               # The main compiler (Lexer -> Parser -> SemanticChecker -> CodeGenVisitor)
├── grammar.ebnf              # EBNF grammar reference
├── ai_usage.txt              # AI interaction log
└── tests/                    # Test suite containing 4 main sets of tests
    ├── run_tests.sh          # Bash script to run all autotests
    ├── run_ll.py             # llvmlite JIT fallback execution script
    ├── valid_*.txt           # Valid programs (compiled and executed)
    ├── invalid_*.txt         # Invalid programs (should produce stderr, no .ll)
    ├── ok/                   # Valid programs (widening, control flow, functions, structs)
    │   └── *.txt             # Valid programs testing all language features
    └── err/                  # Invalid programs (syntax, semantic, type errors)
        └── *.txt             # Invalid programs testing all error cases
```

## Usage

```bash
python compiler.py <source_path> [<output_path>] [--tokens] [--ast | --ast-checked]
```

- `source_path` (Required): Path to the `.txt` source file.
- `output_path` (Optional, defaults to `None`): Path where the generated LLVM IR (`.ll`) will be saved.
- `--tokens` (Optional): Prints the token stream to `stdout` and continues compilation.
- `--ast` (Optional): Prints the Abstract Syntax Tree (AST) to `stdout` and **exits immediately with code 0** (no semantic checking, no code generation, and no `.ll` file is written).
- `--ast-checked` (Optional): Performs semantic checking, prints the checked AST (including generated lambda closure structs), and exits without code generation.

### `--ast` Dump Format
The AST dump uses indentation to represent the tree structure (each level adds 2 spaces):
- `Program` -> children: statements, then `Exit`
- `Struct {name}` -> children: `Field {name} {type} {mut|const}`
- `FnDecl {name}({params}) -> {ret_type}` -> child: body `Block`
- `Decl {name} {type} {mut|const}` -> child: initialization expression(s)
- `Assign {target}` -> child: value expression
- `If` -> children: condition expression, then_block, optional else_block
- `Block` -> children: statements, optional exit
- `While` -> children: condition expression, body_block
- `BinOp {op}` -> children: left expression, right expression
- `Not` -> child: operand expression
- `FieldAccess {field}` -> child: object expression
- `FnCall {name}` -> children: argument expressions
- `Var {name}`
- `Const {val}`
- `Bool {true|false}`
- `Exit` -> child: value expression

## Autotests

Run tests via `tests/run_tests.sh`:
```bash
./tests/run_tests.sh
```