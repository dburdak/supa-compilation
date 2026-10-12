# Supa Compiler

A custom educational compiler for the "Supa" programming language, written in Python with `llvmlite`.

## Practice 5 Features (Control Flow & Scopes)

This version adds support for control flow constructs and block scoping:
- **`if` and `else` statements**: Conditional branching with multi-line blocks `{ ... }`.
- **`while` loops**: Loop construct with condition evaluation and back-edge branching.
- **Unary `!` operator**: Logical NOT for `bool` operands.
- **Block scopes (Stack of Frames)**: Scopes are managed using a stack of frames (`self.scopes`). Variables can be shadowed in inner blocks with any type.
- **Basic Blocks in LLVM IR**: Conditionals and loops generate LLVM basic blocks (`then`, `else`, `merge`, `while_cond`, `while_body`, `while_end`).
- **Entry-Block Allocas**: All variable declarations emit `alloca` instructions exclusively in the entry basic block (`alloca_in_entry`), enabling LLVM `mem2reg` optimization.

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
    ├── ok/                   # Practice 4 & 5 valid programs
    │   └── *.txt             # Valid programs testing widening, scopes, if/else, while
    └── err/                  # Practice 4 & 5 invalid programs
        └── *.txt             # Invalid programs testing semantic/type errors
```

*Note: Alongside `valid_*.txt` files, there may be `.out`, `.ast`, and `.tokens` reference files. Alongside `invalid_*.txt` files, there are `.err` files, and occasionally `.ast` files for programs that are syntactically valid but semantically invalid.*

## Usage

```bash
python compiler.py <source_path> [<output_path>] [--tokens] [--ast]
```

- `source_path` (Required): Path to the `.txt` source file.
- `output_path` (Optional, defaults to `None`): Path where the generated LLVM IR (`.ll`) will be saved.
- `--tokens` (Optional): Prints the token stream to `stdout` and continues compilation.
- `--ast` (Optional): Prints the Abstract Syntax Tree (AST) to `stdout` and **exits immediately with code 0** (no semantic checking, no code generation, and no `.ll` file is written).

### `--ast` Dump Format
The AST dump uses indentation to represent the tree structure (each level adds 2 spaces):
- `Program` -> children: statements, then `Exit`
- `Decl {name} {type} {mut|const}` -> child: initialization expression
- `Assign {name}` -> child: value expression
- `If` -> children: condition expression, then_block, optional else_block
- `Block` -> children: statements, optional exit
- `While` -> children: condition expression, body_block
- `BinOp {op}` -> children: left expression, right expression
- `Not` -> child: operand expression
- `Var {name}`
- `Const {val}`
- `Bool {true|false}`
- `Exit` -> child: value expression

### The Difference Between `--ast` and Full Compilation
When running with `--ast`, the program only executes the Lexer and the Parser. It does not run the `SemanticChecker` or the `CodeGenVisitor`. Therefore, any semantic errors (such as using an undeclared variable, assigning to a constant, invalid type operations, or non-bool conditions) will **not** be caught with `--ast`, and the command will succeed (exit 0) and print the parsed tree.

## Scopes and Frame Stack

The `SemanticChecker` maintains `self.scopes = [{}]`, representing a stack of frames:
- Entering a `Block` (`If` then/else arms, `While` body) pushes an empty dict: `self.scopes.append({})`.
- Exiting a `Block` pops the frame: `self.scopes.pop()`.
- Declarations add variables to `self.scopes[-1]` (top frame), checking only the top frame for duplicate names. Outer variables can be shadowed in inner blocks.
- Variable lookups search from the top frame downwards (`reversed(self.scopes)`).

## Types, Coercion, and Basic Blocks

- **Types**: `i32`, `i64`, `bool` (`i1` in LLVM IR).
- **Coercion**: `i32` automatically widens to `i64` in initializers, assignments, arithmetic (`+`, `-`, `*`), and comparisons (`==`, `!=`).
- **Basic Blocks**: `if` constructs generate `then`, `else` (optional), and `merge` basic blocks. `while` constructs generate `while_cond`, `while_body`, and `while_end` basic blocks with a back-edge `br` instruction.
- **Entry Allocas**: All variable `alloca` instructions are placed at the beginning of the entry basic block (`alloca_in_entry`), allowing LLVM `mem2reg` to optimize memory slots into registers.

## Error Codes

### Lexer & Parser Errors
- **9**: `compilation error: line {line}:{col}: '{' is not closed before the end of the line`
- **10**: `compilation error: line {line}:{col}: unexpected byte {byte}`
- **13**: `compilation error: line {line}:{col}: expected '==' (a single '=' is not an operator)`
- `compilation error: line {line}:{col}: expected '{'`
- `compilation error: line {line}:{col}: block must not be empty`

### SemanticChecker Errors
- **1**: `compilation error: line {line}:{col}: redeclared variable '{name}'`
- **2**: `compilation error: line {line}:{col}: undeclared variable '{name}'`
- **12**: `compilation error: line {line}:{col}: cannot assign to immutable variable '{name}'`
- `compilation error: line {line}:{col}: if condition must be bool, got {cond_type}`
- `compilation error: line {line}:{col}: while condition must be bool, got {cond_type}`
- `compilation error: line {line}:{col}: '!' requires bool operand, got {t}`

## Autotests

Run tests via `tests/run_tests.sh`:
```bash
./tests/run_tests.sh
```