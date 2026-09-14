#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

echo "=== RUNNING SUCCESS TESTS ==="
for test in tests/pass_*.txt; do
    base="${test%.txt}"
    echo "Testing $test..."
    python3 compiler.py "$test" output.ll || exit 1
    llc -filetype=obj output.ll -o output.o
    clang output.o -o program
    ./program > temp.out
    
    if diff -q temp.out "${base}.out" > /dev/null; then
        echo -e "\033[0;32m[PASS]\033[0m"
    else
        echo -e "\033[0;31m[FAIL]\033[0m"
    fi
    rm -f output.ll output.o program temp.out
done

echo -e "\n=== RUNNING FAIL TESTS ==="
for test in tests/fail_*.txt; do
    base="${test%.txt}"
    echo "Testing $test..."
    rm -f output.ll
    python3 compiler.py "$test" output.ll 2> temp.err
    
    if [ ! -f output.ll ] && diff -q temp.err "${base}.err" > /dev/null; then
        echo -e "\033[0;32m[PASS]\033[0m"
    else
        echo -e "\033[0;31m[FAIL]\033[0m"
    fi
    rm -f temp.err
done
