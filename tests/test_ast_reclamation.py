import gc
import runpy
import sys
import weakref
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "compiler.py"
SOURCE = ROOT / "tests" / "opt" / "01_iteration.txt"


def main():
    sys.argv = [str(COMPILER), str(SOURCE)]
    compiler = runpy.run_path(str(COMPILER))

    tree = compiler["Parser"](
        compiler["lex"](SOURCE.read_bytes())
    ).parse_program()
    checker = compiler["SemanticChecker"]()
    tree.accept(checker)

    declaration_type = compiler["DeclNode"]
    removed = next(
        stmt for stmt in tree.stmts
        if isinstance(stmt, declaration_type) and stmt.name == "y"
    )
    reference = weakref.ref(removed)

    compiler["remove_unused_variables"](tree)
    del removed
    assert reference() is not None, "checker should retain the removed declaration"

    del checker
    assert reference() is None, "removed declaration should be released without gc.collect()"
    print("removed DeclNode released immediately after deleting checker (no gc.collect())")


if __name__ == "__main__":
    main()
