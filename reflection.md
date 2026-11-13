# Reflection

1. **The most useful features and patterns**

I found the course material useful in general, especially learning how different programming languages and their compilers handle and improve programs in the background. That knowledge makes it easier to think about what happens under the source code when writing a working program. The most difficult and useful features for me were structures and lambdas. At first, they seemed difficult to control because their behavior depends on how a programmer uses them, but building them made the ideas feel clearer. In `tests/io/points.txt`, the `Point.d2()` method gets `x` and `y` through its receiver, so the values do not need to be passed as separate arguments. The `report(p, d)` function also combines a side effect—printing a point only when the condition is true—with a return value of `1` or `0`. That lets the program both show matches and count them.

2. **Features that were not covered enough**

I think threads and coroutines should be introduced earlier and covered in more detail, including in the required practical work. They are important ideas and seem difficult to build, so I would have liked a practical chance to copy how they work in a language. Compared to this, functions were discussed over several lectures and from different points of view. Giving concurrency ideas similar attention would make them feel less fast and easier to understand.

3. **Three things that surprised me**

First, console input and output did not need us to build complicated tools from the beginning: in the points program, `read()` and `print()` in the end use calls like `scanf` and `printf`. Second, building lambdas was less strange than I expected. The compiler builds a lambda using a created closure structure and a `call` method, instead of needing an unknown tool like a dictionary. Third, I was surprised by how conditional branches are shown in LLVM. An `if` and an `else` are different control-flow paths that can meet at a merge block; a `phi` instruction chooses the value coming from the path that was actually taken. I had expected the compiler to choose a parameter first and then write to the chosen block.

4. **Topics I still want to understand better**

I would like to understand more clearly when `mem2reg` adds `phi` instructions and how it decides which variables need them. I also want to study the ABI in more detail. I understand it as an agreement between callers and called functions, but I am not yet clear about all the other rules it includes besides passing arguments and returning values.

5. **Ideas and suggestions**

I suggest adding regular knowledge checks during the course. They would help students to learn topics as they are introduced instead of leaving them until the end. This is important because simple practical tests and the rules around AI use can make it possible to finish exercises without remembering all the basic ideas. Regular checks could help students review ideas over time and remember them longer.