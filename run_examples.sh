#!/bin/bash
set -euo pipefail

EXAMPLES_DIR="$(dirname "$0")/examples"
PASS=0
FAIL=0

for manga_file in "$EXAMPLES_DIR"/*.manga; do
    base="${manga_file%.manga}"
    output="${base}.png"
    name="$(basename "$manga_file")"

    printf "%-40s" "$name"
    if manga-gen "$manga_file" -o "$output" 2>&1; then
        echo "OK"
        ((PASS++))
    else
        echo "FAIL"
        ((FAIL++))
    fi
done

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ]
