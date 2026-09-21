#!/usr/bin/env bash
# run_tests.sh — runs compiler.py against every test in this folder and
# checks the result against the matching .out (valid_*) or .err (invalid_*) file.
#
# Usage:
#   ./run_tests.sh                 # assumes compiler.py is at ../compiler.py
#   ./run_tests.sh /path/to/compiler.py

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$SCRIPT_DIR"
COMPILER="${1:-$SCRIPT_DIR/../compiler.py}"
PYTHON="${PYTHON:-python3}"

if [ ! -f "$COMPILER" ]; then
    echo "Compiler not found at: $COMPILER"
    echo "Usage: $0 [path/to/compiler.py]"
    exit 2
fi

TMP_LL="$(mktemp /tmp/run_tests_XXXXXX.ll)"
DUMMY_LL="$(mktemp /tmp/run_tests_dummy_XXXXXX.ll)"
trap 'rm -f "$TMP_LL" "$DUMMY_LL"' EXIT

PASS=0
FAIL=0

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'

# Reruns the compiler as a Python module (instead of a subprocess) so we can
# reach into its `lines` variable (the token stream from lex()) and print
# each token with the project's own Token.to_str(), the same format .out
# files are written in. This only runs for programs the CLI already accepted.
dump_tokens() {
    local src="$1"
    "$PYTHON" - "$COMPILER" "$src" "$DUMMY_LL" <<'PYEOF'
import sys, importlib.util

compiler_path, source_path, dummy_out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [compiler_path, source_path, dummy_out]

spec = importlib.util.spec_from_file_location("compiler_under_test", compiler_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

for line in mod.lines:
    for tok in line:
        sys.stdout.write(tok.to_str())
PYEOF
}

run_valid() {
    local name="$1"
    local txt="$TESTS_DIR/${name}.txt"
    local expected_out="$TESTS_DIR/${name}.out"

    if [ ! -f "$expected_out" ]; then
        echo -e "${YELLOW}SKIP${NC} $name: no ${name}.out file found"
        return
    fi

    local stderr_output exit_code
    stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler exited with code $exit_code (expected 0)"
        [ -n "$stderr_output" ] && echo "       stderr: $stderr_output"
        FAIL=$((FAIL + 1))
        return
    fi

    local actual_out expected_content
    actual_out="$(dump_tokens "$txt")"
    expected_content="$(cat "$expected_out")"

    if [ "$actual_out" == "$expected_content" ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} $name: token stream differs from ${name}.out"
        diff <(echo "$actual_out") <(echo "$expected_content") | sed 's/^/       /'
        FAIL=$((FAIL + 1))
    fi
}

run_invalid() {
    local name="$1"
    local txt="$TESTS_DIR/${name}.txt"
    local expected_err="$TESTS_DIR/${name}.err"

    if [ ! -f "$expected_err" ]; then
        echo -e "${YELLOW}SKIP${NC} $name: no ${name}.err file found"
        return
    fi

    local actual_err exit_code expected_content
    actual_err=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?
    expected_content="$(cat "$expected_err")"

    if [ "$exit_code" -eq 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler unexpectedly succeeded (exit 0), expected an error"
        FAIL=$((FAIL + 1))
        return
    fi

    if [ "$actual_err" == "$expected_content" ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} $name: stderr differs from ${name}.err"
        echo "       expected: $expected_content"
        echo "       actual:   $actual_err"
        FAIL=$((FAIL + 1))
    fi
}

echo "Tests dir: $TESTS_DIR"
echo "Compiler:  $COMPILER"
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
