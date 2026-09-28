#!/usr/bin/env bash
# run_tests.sh — runs compiler.py against test files.
#
# It tests 4 categories:
# 1. tests/valid_*.txt: must exit 0, write .ll, execute via lli or run_ll.py, and exact match .out
#    (after stripping "Program exit with result " prefix if present to normalize).
#    If .ast / .tokens exist, they must exactly match --ast / --tokens output.
# 2. tests/invalid_*.txt: must exit non-zero, exact match stderr with .err, write NO .ll file.
#    If .ast exists, --ast must SUCCEED (exit 0) and exactly match.
# 3. tests/ok/*.txt: must exit 0, write .ll, execute, exact match .expected.
# 4. tests/err/*.txt: must exit non-zero, exact match stderr with .expected, write NO .ll.

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
    "$PYTHON" "$COMPILER" --tokens "$1" 2>/dev/null
}

dump_ast() {
    "$PYTHON" "$COMPILER" --ast "$1" 2>/dev/null
}

normalize_output() {
    local val="$1"
    val="${val#Program exit with result }"
    echo -n "$val"
}

run_valid_test() {
    local txt="$1"
    local expected_out_file="$2"
    local expected_ast_file="${txt%.txt}.ast"
    local expected_tokens_file="${txt%.txt}.tokens"
    local name="$(basename "$(dirname "$txt")")/$(basename "$txt")"
    name="${name#./}"
    
    rm -f "$TMP_LL"
    
    local stderr_output exit_code
    stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler exited with code $exit_code (expected 0)"
        echo "       stderr: $stderr_output"
        FAIL=$((FAIL + 1))
        return
    fi
    
    local actual_out expected_out norm_actual norm_expected
    actual_out=$(execute_ir "$TMP_LL")
    expected_out=$(cat "$expected_out_file")
    
    norm_actual=$(normalize_output "$actual_out")
    norm_expected=$(normalize_output "$expected_out")
    
    if [ "$norm_actual" != "$norm_expected" ]; then
        echo -e "${RED}FAIL${NC} $name: runtime output mismatch"
        echo "       expected: '$norm_expected'"
        echo "       actual:   '$norm_actual'"
        FAIL=$((FAIL + 1))
        return
    fi
    
    if [ -f "$expected_tokens_file" ]; then
        local actual_tokens expected_tokens
        actual_tokens=$(dump_tokens "$txt")
        expected_tokens=$(cat "$expected_tokens_file")
        if [ "$actual_tokens" != "$expected_tokens" ]; then
            echo -e "${RED}FAIL${NC} $name: --tokens mismatch"
            FAIL=$((FAIL + 1))
            return
        fi
    fi

    if [ -f "$expected_ast_file" ]; then
        local actual_ast expected_ast
        actual_ast=$(dump_ast "$txt")
        expected_ast=$(cat "$expected_ast_file")
        if [ "$actual_ast" != "$expected_ast" ]; then
            echo -e "${RED}FAIL${NC} $name: --ast mismatch"
            FAIL=$((FAIL + 1))
            return
        fi
    fi

    echo -e "${GREEN}PASS${NC} $name"
    PASS=$((PASS + 1))
}

run_invalid_test() {
    local txt="$1"
    local expected_err_file="$2"
    local expected_ast_file="${txt%.txt}.ast"
    local name="$(basename "$(dirname "$txt")")/$(basename "$txt")"
    name="${name#./}"
    
    rm -f "$TMP_LL"
    
    local actual_err exit_code
    actual_err=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1)
    exit_code=$?
    
    if [ "$exit_code" -eq 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler succeeded but should have failed"
        FAIL=$((FAIL + 1))
        return
    fi
    
    local expected_err
    expected_err=$(cat "$expected_err_file")
    
    if [ "$actual_err" != "$expected_err" ]; then
        echo -e "${RED}FAIL${NC} $name: stderr mismatch"
        echo "       expected: '$expected_err'"
        echo "       actual:   '$actual_err'"
        FAIL=$((FAIL + 1))
        return
    fi
    
    if [ -f "$TMP_LL" ]; then
        echo -e "${RED}FAIL${NC} $name: produced .ll file despite error"
        FAIL=$((FAIL + 1))
        return
    fi
    
    if [ -f "$expected_ast_file" ]; then
        local actual_ast ast_exit expected_ast
        actual_ast=$("$PYTHON" "$COMPILER" --ast "$txt" 2>&1)
        ast_exit=$?
        
        if [ "$ast_exit" -ne 0 ]; then
            echo -e "${RED}FAIL${NC} $name: --ast failed with code $ast_exit but should succeed for semantic errors"
            FAIL=$((FAIL + 1))
            return
        fi
        
        expected_ast=$(cat "$expected_ast_file")
        if [ "$actual_ast" != "$expected_ast" ]; then
            echo -e "${RED}FAIL${NC} $name: --ast mismatch for semantic test"
            FAIL=$((FAIL + 1))
            return
        fi
    fi
    
    echo -e "${GREEN}PASS${NC} $name"
    PASS=$((PASS + 1))
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
    if [ -f "${f%.txt}.out" ]; then
        run_valid_test "$f" "${f%.txt}.out"
    else
        echo -e "${YELLOW}SKIP${NC} $(basename "$f"): no .out file found"
    fi
done

for f in "$TESTS_DIR"/invalid_*.txt; do
    [ -e "$f" ] || continue
    if [ -f "${f%.txt}.err" ]; then
        run_invalid_test "$f" "${f%.txt}.err"
    else
        echo -e "${YELLOW}SKIP${NC} $(basename "$f"): no .err file found"
    fi
done

for f in "$TESTS_DIR"/ok/*.txt; do
    [ -e "$f" ] || continue
    if [ -f "${f%.txt}.expected" ]; then
        run_valid_test "$f" "${f%.txt}.expected"
    else
        echo -e "${YELLOW}SKIP${NC} $(basename "$f"): no .expected file found"
    fi
done

for f in "$TESTS_DIR"/err/*.txt; do
    [ -e "$f" ] || continue
    if [ -f "${f%.txt}.expected" ]; then
        run_invalid_test "$f" "${f%.txt}.expected"
    else
        echo -e "${YELLOW}SKIP${NC} $(basename "$f"): no .expected file found"
    fi
done

echo "----------------------------------------"
echo -e "Passed: ${GREEN}${PASS}${NC}   Failed: ${RED}${FAIL}${NC}"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
