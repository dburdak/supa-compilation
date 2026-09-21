#!/usr/bin/env bash
# run_tests.sh — runs compiler.py against every test in this folder,
# executes the LLVM IR, and checks the result against the matching .out file.

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
trap 'rm -f "$TMP_LL"' EXIT

PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

run_valid() {
    local name="$1"
    local txt="$TESTS_DIR/${name}.txt"
    local expected_out="$TESTS_DIR/${name}.out"

    if [ ! -f "$expected_out" ]; then
        echo -e "${YELLOW}SKIP${NC} $name: no ${name}.out file found"
        return
    fi

    # 1. Запускаємо компілятор (генеруємо LLVM IR у $TMP_LL)
    local stderr_output exit_code
    stderr_output=$("$PYTHON" "$COMPILER" "$txt" "$TMP_LL" 2>&1 1>/dev/null)
    exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: compiler exited with code $exit_code (expected 0)"
        [ -n "$stderr_output" ] && echo "       stderr: $stderr_output"
        
        # Виводимо токени для зручного дебагу
        echo "       Tokens stream:"
        "$PYTHON" "$COMPILER" --tokens "$txt" "$TMP_LL" | sed 's/^/         /'
        
        FAIL=$((FAIL + 1))
        return
    fi

    # 2. Виконуємо згенерований код за допомогою lli (LLVM interpreter)
    local actual_out expected_content lli_exit
    actual_out=$(lli "$TMP_LL" 2>&1)
    lli_exit=$?

    if [ "$lli_exit" -ne 0 ]; then
        echo -e "${RED}FAIL${NC} $name: execution (lli) failed with code $lli_exit"
        echo "       output: $actual_out"
        FAIL=$((FAIL + 1))
        return
    fi

    expected_content="$(cat "$expected_out")"

    # 3. Порівнюємо результат виконання із .out файлом
    if [ "$actual_out" == "$expected_content" ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} $name: execution result differs from ${name}.out"
        echo "       expected: $expected_content"
        echo "       actual:   $actual_out"
        
        # Виводимо токени, щоб побачити, як програма розбила код, що дав неправильний результат
        echo "       Tokens stream:"
        "$PYTHON" "$COMPILER" --tokens "$txt" "$TMP_LL" | sed 's/^/         /'
        
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
    # Запускаємо компілятор, очікуємо помилку
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
