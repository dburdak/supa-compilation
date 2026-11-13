#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IO_DIR="$SCRIPT_DIR/io"
COMPILER="${1:-$SCRIPT_DIR/../compiler.py}"
PYTHON="${PYTHON:-python3}"
LLC="${LLC:-llc}"
CLANG="${CLANG:-clang}"
OPT="${OPT:-both}"

if [[ "$OPT" != "0" && "$OPT" != "1" && "$OPT" != "both" ]]; then
    echo "OPT must be 0, 1, or both (got '$OPT')" >&2
    exit 2
fi

if [[ ! -f "$COMPILER" ]]; then
    echo "Compiler not found at: $COMPILER" >&2
    exit 2
fi
for tool in "$LLC" "$CLANG"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Required native build tool not found: $tool" >&2
        exit 2
    fi
done

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/supa_io_tests.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS=0
FAIL=0

compile_source() {
    local mode="$1" source="$2" ll_file="$3"
    if [[ "$mode" == "1" ]]; then
        "$PYTHON" "$COMPILER" --remove-unused "$source" "$ll_file"
    else
        "$PYTHON" "$COMPILER" "$source" "$ll_file"
    fi
}

run_mode() {
    local mode="$1"
    local source name input expected actual ll_file obj_file binary

    for source in "$IO_DIR"/*.txt; do
        [[ -e "$source" ]] || continue
        name="$(basename "${source%.txt}")"
        ll_file="$TMP_DIR/$name.$mode.ll"
        obj_file="$TMP_DIR/$name.$mode.o"
        binary="$TMP_DIR/$name.$mode"

        if ! compile_source "$mode" "$source" "$ll_file"; then
            echo "FAIL io/$name (OPT=$mode): compiler failed"
            FAIL=$((FAIL + 1))
            continue
        fi
        if ! "$LLC" -filetype=obj -relocation-model=pic "$ll_file" -o "$obj_file"; then
            echo "FAIL io/$name (OPT=$mode): llc failed"
            FAIL=$((FAIL + 1))
            continue
        fi
        if ! "$CLANG" -fPIE "$obj_file" -o "$binary"; then
            echo "FAIL io/$name (OPT=$mode): clang failed"
            FAIL=$((FAIL + 1))
            continue
        fi

        for input in "$IO_DIR/$name".*.in; do
            [[ -e "$input" ]] || continue
            expected="${input%.in}.expected"
            actual="$TMP_DIR/$(basename "${input%.in}").$mode.actual"
            if [[ ! -f "$expected" ]]; then
                echo "FAIL $(basename "${input%.in}"): missing expected output"
                FAIL=$((FAIL + 1))
                continue
            fi
            if ! "$binary" < "$input" > "$actual"; then
                echo "FAIL $(basename "${input%.in}") (OPT=$mode): program failed"
                FAIL=$((FAIL + 1))
                continue
            fi
            if ! cmp -s "$actual" "$expected"; then
                echo "FAIL $(basename "${input%.in}") (OPT=$mode): output mismatch"
                diff -u "$expected" "$actual" || true
                FAIL=$((FAIL + 1))
                continue
            fi
            echo "PASS io/$(basename "${input%.in}") (OPT=$mode)"
            PASS=$((PASS + 1))
        done
    done
}

if [[ "$OPT" == "0" || "$OPT" == "both" ]]; then
    run_mode 0
fi
if [[ "$OPT" == "1" || "$OPT" == "both" ]]; then
    run_mode 1
fi

echo "I/O sessions passed: $PASS   failed: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
