# Benchmark: arithmetic loop (CPU-bound) — plain Python equivalent
total = 0
n = 2000000
for i in range(n):
    total += (i * 3 + 7) % 1000
print(total)
