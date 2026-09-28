#!/usr/bin/env bash
# run_tests.sh — runs compiler.py against every test in this folder.
#
# For valid_*.txt:
#   1. compiler.py must exit 0 and produce a .ll file
#   2. running that IR must print exactly what valid_*.out says
#      (uses `lli` if it's on PATH, otherwise falls back to the bundled
#      run_ll.py, which JIT-executes the module via llvmlite itself —
#      handy when the LLVM command-line tools aren't installed)
#   3. `compiler.py --tokens` must match valid_*.tokens   (if that file exists)
#   4. `compiler.py --ast`    must match valid_*.ast      (if that file exists)
#
# For invalid_*.txt:
#   1. compiler.py must exit non-zero
#   2. its stderr must match invalid_*.err exactly
#   3. no .ll file may be produced
#   4. if a matching invalid_*.ast file exists, `--ast` is checked too and is
#      EXPECTED TO SUCCEED — semantic checks (redeclaration, use-before-decl,
#      assignment to a const, missing exit) live in the codegen walk, not in
#      the parser, so a program that is syntactically valid but semantically
#      wrong must still produce a correct tree under --ast.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$SCRIPT_DIR"
COMPILER="${1:-$SCRIPT_DIR/../compiler.py}"
PYTHON="${PYTHON:-python3}"
RUN_LL="$SCRIPT_DIR/run_ll.py"

if [ ! -f "$COMPILER" ]; then
    echo "Compiler not found at: $COMPILER"
    echo "Usage: $0 [path/to/compiler.py]"
    exit 2
fi

TMP_LL="$(mktemp /tmp/run_tests_XXXXXX.ll)"
trap 'rm -f "$TMP_LL"' EXIT

PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Execute a .ll file and print what the program wrote to stdout.
# Prefers the real `lli`; falls back to the bundled llvmlite JIT runner.
execute_ir() {
    local ll_path="$1"
    if command -v lli >/dev/null 2>&1; then
        lli "$ll_path" 2>&1
    elif [ -f "$RUN_LL" ]; then
        "$PYTHON" "$RUN_LL" "$ll_path" 2>&1
    else
        echo "ERROR: neither 'lli' nor $RUN_LL is available to execute the IR" >&2
        return 127
    fi
}

dump_tokens() {
    "$PYTHON" "$COMPILER" --tokens "$1" "$TMP_LL" 2>/dev/null
}

dump_ast() {
    "$PYTHON" "$COMPILER" --ast "$1" 2>/dev/null
}

# Compares $1 (actual, already captured) against the contents of file $2.
# Echoes a diff (indented) when they differ. Returns 0/1.
matches_file() {
    local actual="$1" expected_file="$2"
    [ "$actual" == "$(cat "$expected_file")" ]
}

run_valid() {
    local name="$1"
    local txt="$TESTS_DIR/${name}.txt"
    local expected_out="$TESTS_DIR/${name}.out"
    local expected_ast="$TESTS_DIR/${name}.ast"
    local expected_tokens="$TESTS_DIR/${name}.tokens"
    local ok=1

    if [ ! -f "$expected_out" ]; then
        echo -e "${YELLOW}SKIP${NC} $name: no ${name}.out file found"
        return
    fi

    # 1. full compile must succeed
    local stderr_output exit_code
    stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler exited with code $exit_code (expected 0)"
        [ -n "$stderr_output" ] && echo "       stderr: $stderr_output"
        echo "       Tokens stream:"
        dump_tokens "$txt" | sed 's/^/         /'
        FAIL=$((FAIL + 1))
        return
    fi

    # 2. execute the IR, compare against .out
    local actual_out expected_content
    actual_out=$(execute_ir "$TMP_LL")
    expected_content="$(cat "$expected_out")"
    if [ "$actual_out" != "$expected_content" ]; then
        echo -e "${RED}FAIL${NC} $name: execution result differs from ${name}.out"
        echo "       expected: $expected_content"
        echo "       actual:   $actual_out"
        ok=0
    fi

    # 3. --tokens, if a reference file exists
    if [ -f "$expected_tokens" ]; then
        local actual_tokens
        actual_tokens=$(dump_tokens "$txt")
        if ! matches_file "$actual_tokens" "$expected_tokens"; then
            echo -e "${RED}FAIL${NC} $name: --tokens output differs from ${name}.tokens"
            diff <(echo "$actual_tokens") "$expected_tokens" | sed 's/^/       /'
            ok=0
        fi
    fi

    # 4. --ast, if a reference file exists
    if [ -f "$expected_ast" ]; then
        local actual_ast
        actual_ast=$(dump_ast "$txt")
        if ! matches_file "$actual_ast" "$expected_ast"; then
            echo -e "${RED}FAIL${NC} $name: --ast output differs from ${name}.ast"
            diff <(echo "$actual_ast") "$expected_ast" | sed 's/^/       /'
            ok=0
        fi
    fi

    if [ "$ok" -eq 1 ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
}

run_invalid() {
    local name="$1"
    local txt="$TESTS_DIR/${name}.txt"
    local expected_err="$TESTS_DIR/${name}.err"
    local expected_ast="$TESTS_DIR/${name}.ast"
    local ok=1

    if [ ! -f "$expected_err" ]; then
        echo -e "${YELLOW}SKIP${NC} $name: no ${name}.err file found"
        return
    fi

    # 1 & 2. compiler must fail, stderr must match
    # (TMP_LL is reused across tests — clear it first so a leftover .ll from
    # an earlier *valid* test can't be mistaken for one this run wrote)
    : > "$TMP_LL"
    local actual_err exit_code expected_content
    actual_err=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?
    expected_content="$(cat "$expected_err")"

    if [ "$exit_code" -eq 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler unexpectedly succeeded (exit 0), expected an error"
        FAIL=$((FAIL + 1))
        return
    fi

    if [ "$actual_err" != "$expected_content" ]; then
        echo -e "${RED}FAIL${NC} $name: stderr differs from ${name}.err"
        echo "       expected: $expected_content"
        echo "       actual:   $actual_err"
        ok=0
    fi

    # 3. no .ll file must be left behind (the compiler must not write output on error)
    if [ -s "$TMP_LL" ]; then
        echo -e "${RED}FAIL${NC} $name: an .ll file was written despite the compilation error"
        ok=0
    fi

    # 4. some semantic errors (redeclaration, use-before-decl, const assignment,
    #    missing exit) only fire during codegen, so --ast must still succeed
    #    and match the reference tree for those specific tests.
    if [ -f "$expected_ast" ]; then
        local ast_out ast_exit
        ast_out=$("$PYTHON" "$COMPILER" --ast "$txt" 2>&1)
        ast_exit=$?
        if [ "$ast_exit" -ne 0 ]; then
            echo -e "${RED}FAIL${NC} $name: --ast unexpectedly failed (expected it to parse fine)"
            echo "       output: $ast_out"
            ok=0
        elif ! matches_file "$ast_out" "$expected_ast"; then
            echo -e "${RED}FAIL${NC} $name: --ast output differs from ${name}.ast"
            diff <(echo "$ast_out") "$expected_ast" | sed 's/^/       /'
            ok=0
        fi
    fi

    if [ "$ok" -eq 1 ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
}

echo "Tests dir: $TESTS_DIR"
echo "Compiler:  $COMPILER"
if command -v lli >/dev/null 2>&1; then
    echo "Executor:  lli ($(command -v lli))"
else
    echo "Executor:  $RUN_LL (llvmlite JIT fallback — 'lli' not found on PATH)"
fi
echo

for f in "$TESTS_DIR"/valid_*.txt; do
    [ -e "$f" ] || continue
    run_valid "$(basename "$f" .txt)"
done

for f in "$TESTS_DIR"/invalid_*.txt; do
    [ -e "$f" ] || continue
    run_invalid "$(basename "$f" .txt)"
done

echo
echo "----------------------------------------"
echo -e "Passed: ${GREEN}${PASS}${NC}   Failed: ${RED}${FAIL}${NC}"

[ "$FAIL" -eq 0 ]
