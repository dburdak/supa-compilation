#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FFI_DIR="$SCRIPT_DIR/ffi"
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

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/supa_ffi_tests.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS=0
FAIL=0

run_mode() {
    local mode="$1"
    local source name c_source ll_file object binary input expected actual
    for source in "$FFI_DIR"/*.txt; do
        [[ -e "$source" ]] || continue
        name="$(basename "${source%.txt}")"
        c_source="$FFI_DIR/$name.c"
        ll_file="$TMP_DIR/$name.$mode.ll"
        object="$TMP_DIR/$name.$mode.o"
        binary="$TMP_DIR/$name.$mode"

        if [[ "$mode" == "1" ]]; then
            if ! "$PYTHON" "$COMPILER" --remove-unused "$source" "$ll_file"; then
                echo "FAIL ffi/$name (OPT=$mode): compiler failed"
                FAIL=$((FAIL + 1))
                continue
            fi
        elif ! "$PYTHON" "$COMPILER" "$source" "$ll_file"; then
            echo "FAIL ffi/$name (OPT=$mode): compiler failed"
            FAIL=$((FAIL + 1))
            continue
        fi
        if ! "$LLC" -filetype=obj -relocation-model=pic "$ll_file" -o "$object"; then
            echo "FAIL ffi/$name (OPT=$mode): llc failed"
            FAIL=$((FAIL + 1))
            continue
        fi
        if ! "$CLANG" -fPIE "$object" "$c_source" -o "$binary"; then
            echo "FAIL ffi/$name (OPT=$mode): clang link failed"
            FAIL=$((FAIL + 1))
            continue
        fi

        for input in "$FFI_DIR/$name".*.in; do
            [[ -e "$input" ]] || continue
            expected="${input%.in}.expected"
            actual="$TMP_DIR/$(basename "${input%.in}").$mode.actual"
            if [[ ! -f "$expected" ]]; then
                echo "FAIL $(basename "${input%.in}"): missing expected output"
                FAIL=$((FAIL + 1))
                continue
            fi
            if ! "$binary" < "$input" > "$actual"; then
                echo "FAIL ffi/$(basename "${input%.in}") (OPT=$mode): program failed"
                FAIL=$((FAIL + 1))
                continue
            fi
            if ! cmp -s "$actual" "$expected"; then
                echo "FAIL ffi/$(basename "${input%.in}") (OPT=$mode): output mismatch"
                diff -u "$expected" "$actual" || true
                FAIL=$((FAIL + 1))
                continue
            fi
            echo "PASS ffi/$(basename "${input%.in}") (OPT=$mode)"
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

echo "FFI sessions passed: $PASS   failed: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
