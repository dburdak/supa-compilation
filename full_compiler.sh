#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
LLC="${LLC:-llc}"
CLANG="${CLANG:-clang}"
REMOVE_UNUSED=0

if [[ "${1:-}" == "--remove-unused" ]]; then
    REMOVE_UNUSED=1
    shift
fi

if [[ "$#" -gt 0 ]]; then
    echo "Usage: $0 [--remove-unused]" >&2
    exit 2
fi

cd "$ROOT_DIR"
if [[ "$REMOVE_UNUSED" == "1" ]]; then
    "$PYTHON" compiler.py --remove-unused tests/io/points.txt points.ll
else
    "$PYTHON" compiler.py tests/io/points.txt points.ll
fi
"$LLC" -filetype=obj -relocation-model=pic points.ll -o points.o
"$CLANG" -fPIE points.o -o points
exec ./points
