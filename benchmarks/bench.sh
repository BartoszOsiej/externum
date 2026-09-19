#!/usr/bin/env bash
# Benchmark: arithmetic loop (CPU-bound) — plain bash equivalent
total=0
for ((i = 0; i < 2000000; i++)); do
    total=$(( total + (i * 3 + 7) % 1000 ))
done
echo "$total"
