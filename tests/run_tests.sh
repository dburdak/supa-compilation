#!/usr/bin/env bash
# run_tests.sh — runs compiler.py against test files.
#
# It tests 4 categories:
# 1. tests/valid_*.txt: must exit 0, write .ll, execute via lli or run_ll.py, and exactly match .out.
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
    local input_file="${2:-}"
    if command -v lli >/dev/null 2>&1; then
        if [ -n "$input_file" ] && [ -f "$input_file" ]; then
            lli "$ll_path" < "$input_file" 2>&1
        else
            lli "$ll_path" 2>&1
        fi
    elif [ -f "$RUN_LL" ]; then
        if [ -n "$input_file" ] && [ -f "$input_file" ]; then
            "$PYTHON" "$RUN_LL" "$ll_path" < "$input_file" 2>&1
        else
            "$PYTHON" "$RUN_LL" "$ll_path" 2>&1
        fi
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
    
    local actual_out expected_out
    local input_file="${txt%.txt}.in"
    actual_out=$(execute_ir "$TMP_LL" "$input_file")
    expected_out=$(cat "$expected_out_file")
    
    if [ "$actual_out" != "$expected_out" ]; then
        echo -e "${RED}FAIL${NC} $name: runtime output mismatch"
        echo "       expected: '$expected_out'"
        echo "       actual:   '$actual_out'"
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

    rm -f "$TMP_LL"
    stderr_output=$("$PYTHON" "$COMPILER" --remove-unused "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: optimized compiler exited with code $exit_code"
        echo "       stderr: $stderr_output"
        FAIL=$((FAIL + 1))
        return
    fi
    actual_out=$(execute_ir "$TMP_LL" "$input_file")
    if [ "$actual_out" != "$expected_out" ]; then
        echo -e "${RED}FAIL${NC} $name: optimized runtime output mismatch"
        echo "       expected: '$expected_out'"
        echo "       actual:   '$actual_out'"
        FAIL=$((FAIL + 1))
        return
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

    actual_err=$("$PYTHON" "$COMPILER" --remove-unused "$txt" "$TMP_LL" 2>&1)
    exit_code=$?
    if [ "$exit_code" -eq 0 ] || [ "$actual_err" != "$expected_err" ] || [ -f "$TMP_LL" ]; then
        echo -e "${RED}FAIL${NC} $name: --remove-unused changed invalid-program handling"
        FAIL=$((FAIL + 1))
        return
    fi
    
    echo -e "${GREEN}PASS${NC} $name"
    PASS=$((PASS + 1))
}

run_opt_test() {
    local txt="$1"
    local expected_out_file="${txt%.txt}.expected"
    local expected_ast_file="${txt%.txt}.astc"
    local checks_file="${txt%.txt}.checks"
    local name="opt/$(basename "$txt")"
    local baseline_out optimized_out checked_ast expected_out

    rm -f "$TMP_LL"
    local stderr_output exit_code
    stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: baseline compiler exited with code $exit_code"
        echo "       stderr: $stderr_output"
        FAIL=$((FAIL + 1))
        return
    fi
    baseline_out=$(execute_ir "$TMP_LL" "${txt%.txt}.in")

    rm -f "$TMP_LL"
    case "$(basename "$txt")" in
        01_*)
            stderr_output=$("$PYTHON" "$COMPILER" --remove-unused "$txt" "$TMP_LL" 2>&1 1>/dev/null)
            ;;
        02_*)
            stderr_output=$("$PYTHON" "$COMPILER" "$txt" --remove-unused "$TMP_LL" 2>&1 1>/dev/null)
            ;;
        03_*)
            stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" --remove-unused 2>&1 1>/dev/null)
            ;;
        *)
            stderr_output=$("$PYTHON" "$COMPILER" --remove-unused "$txt" "$TMP_LL" 2>&1 1>/dev/null)
            ;;
    esac
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: optimized compiler exited with code $exit_code"
        echo "       stderr: $stderr_output"
        FAIL=$((FAIL + 1))
        return
    fi
    optimized_out=$(execute_ir "$TMP_LL" "${txt%.txt}.in")
    expected_out=$(cat "$expected_out_file")
    if [ "$baseline_out" != "$expected_out" ] || [ "$optimized_out" != "$expected_out" ]; then
        echo -e "${RED}FAIL${NC} $name: output mismatch"
        echo "       expected: '$expected_out'"
        echo "       baseline: '$baseline_out'"
        echo "       optimized: '$optimized_out'"
        FAIL=$((FAIL + 1))
        return
    fi

    checked_ast=$("$PYTHON" "$COMPILER" --remove-unused --ast-checked "$txt" 2>&1)
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: --ast-checked failed with code $exit_code"
        FAIL=$((FAIL + 1))
        return
    fi
    local expected_ast
    expected_ast=$(cat "$expected_ast_file")
    if [ "$checked_ast" != "$expected_ast" ]; then
        echo -e "${RED}FAIL${NC} $name: --ast-checked mismatch"
        FAIL=$((FAIL + 1))
        return
    fi
    if [ -f "$checks_file" ]; then
        while IFS='|' read -r mode expected text; do
            [ -n "$mode" ] || continue
            local count
            count=$(printf '%s\n' "$checked_ast" | grep -F -c -- "$text" || true)
            if { [ "$mode" = "contains" ] && [ "$count" -lt 1 ]; } ||
               { [ "$mode" = "absent" ] && [ "$count" -ne 0 ]; } ||
               { [ "$mode" = "count" ] && [ "$count" -ne "$expected" ]; }; then
                echo -e "${RED}FAIL${NC} $name: AST check '$mode|$expected|$text' failed"
                FAIL=$((FAIL + 1))
                return
            fi
        done < "$checks_file"
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

for f in "$TESTS_DIR"/opt/*.txt; do
    [ -e "$f" ] || continue
    if [ -f "${f%.txt}.expected" ] && [ -f "${f%.txt}.astc" ]; then
        run_opt_test "$f"
    else
        echo -e "${RED}FAIL${NC} $(basename "$f"): missing .expected or .astc file"
        FAIL=$((FAIL + 1))
    fi
done

echo "----------------------------------------"
echo -e "Passed: ${GREEN}${PASS}${NC}   Failed: ${RED}${FAIL}${NC}"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
