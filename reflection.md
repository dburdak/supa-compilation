# Course Reflection

1. **The most useful features and patterns**

I found the course material useful overall, especially learning how different programming languages and their compilers process and optimize programs behind the scenes. The features that seemed hardest to implement, and therefore most useful to understand, were structures and lambdas. In `tests/io/points.txt`, `Point.d2()` reads `x` and `y` through its receiver instead of receiving the coordinates as explicit arguments. In the same file, `report(p, d)` prints a point only when the condition is true and returns `1` or `0`; this combines an observable action with a value that the caller can use to count matches. Seeing both ideas in one working program made them feel less abstract.

2. **Features that were not covered enough**

I would like threads and coroutines to receive more attention in lectures and in practical work. The current language grammar in `grammar.ebnf` describes structures, functions, statements, and control flow, but has no thread or coroutine constructs. I suggest adding a separate practical, or a substantial task within one of the practicals, where we reproduce this kind of mechanism in a small language. Functions were discussed from several angles over multiple lectures, so I think concurrency deserves a similarly concrete opportunity for implementation.

3. **Three things that surprised me**

First, I was surprised that console I/O could be implemented by declaring and calling C functions rather than building a large input/output mechanism from scratch. In `compiler.py`, the module declares `printf` and `scanf`; `CodeGenVisitor.visit_print` and `visit_fn_call` emit the corresponding calls. Second, lambdas were simpler to understand than I expected: `SemanticChecker.visit_lambda` lowers one to a generated closure structure with a `call` method, as also illustrated by `tests/ok/lambda_capture_lambda.txt`. Third, the LLVM control-flow explanation surprised me. `CodeGenVisitor.visit_if` creates alternative `then` and `else` blocks that can branch to a `merge` block, as exercised by `tests/ok/if_else.txt`. I had expected the compiler to select a value in advance; instead, LLVM can use a `phi` instruction at a merge point to select the value associated with the path that arrived there.

4. **Concepts I still want to understand better**

I want to understand when LLVM's `mem2reg` inserts `phi` instructions and how it decides which variables need them. A useful place to connect that question to the project is `CodeGenVisitor.visit_if`: it builds the branch and merge blocks, but this compiler does not itself emit a `phi` there. I would also like a broader explanation of the ABI. The `extern` checks in `SemanticChecker._register_fn_sig` currently limit C parameters and results to `i32` and `i64`; I want to learn what additional platform and calling-convention rules matter beyond passing arguments and returning values.

5. **Ideas and suggestions**

I suggest adding regular knowledge checks throughout the course rather than relying mainly on a final assessment. For example, short checks after each major topic could accompany the implementation tests run by `tests/run_tests.sh`. Those tests verify that programs compile and produce the expected output, but they do not necessarily show whether a student understands the concepts behind the result. Regular checks could encourage students to learn continuously and help the material stay memorable.
