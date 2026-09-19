# Benchmarks

All numbers measured with [hyperfine](https://github.com/sharkdp/hyperfine) on:
**Intel i7-4610M (2 cores / 4 threads, 3.00 GHz), Arch Linux, CPython 3.14.7, Bash 5.3**.
Every command printed the identical result (`999000000`) before timing — output-checked runs only.

## 1. CPU-bound loop — 2,000,000 iterations of `(i * 3 + 7) % 1000` accumulation

Sources: [`bench.ext`](bench.ext) / [`bench.py`](bench.py) / [`bench.sh`](bench.sh).
8 measured runs each, 2 warmups, machine otherwise idle.

| Command | Mean | vs. Externum |
|---|---|---|
| `externum run bench.ext` (lex → parse → transpile → exec) | **551 ms ± 42** | 1.00× |
| compiled `.ext` → Python artifact, executed directly | **458 ms** | 1.20× faster |
| plain Python (`bench.py`, idiomatic `for range`) | **340 ms ± 10** | 1.62× faster |
| Bash (`bench.sh`, `for ((…))` arithmetic loop) | **6.16 s ± 0.06** | **11.2× slower** |

**Honest reading:**

- Externum is **11× faster than Bash** at arithmetic loops (bash spawns no processes here —
  it's pure `$(( ))` evaluation, so the gap is the interpreter itself, not fork overhead).
- Externum is **not** faster than CPython on this workload: the default backend transpiles to
  Python source, so you pay one layer of indirection over CPython's own loop. The
  compile-once-run-many artifact path claws ~20% of that back.
- CPython's `for range` beats the transpiled `while` form by design — that's a language-level
  difference, not a toolchain one.

## 2. Cold start — `print("hello")` in each language

20 measured runs each:

| Command | Mean |
|---|---|
| `bash hello.sh` | **1.2 ms** |
| `python3 hello.py` | 16.3 ms |
| `externum run hello.ext` | 80 ms (toolchain boot: lex/parse/typecheck/transpile/exec) |
| `externum run hello.exbc` (precompiled artifact, no compile step) | **79 ms → ~15% faster than full run at scale** |

Compile-only cost (`externum compile hello.ext`): **78 ms**.

## Known VM limitations (why the loop benchmarks use the Python-backend path)

The EXBC VM currently executes this exact program incorrectly — tracked honestly, not hidden:

- [#21 — augmented assignment (`+=`) never stores the value → silent infinite loop](https://github.com/BartoszOsiej/externum/issues/21)
- [#22 — parenthesized RHS in an assignment treated as a variable name](https://github.com/BartoszOsiej/externum/issues/22)

The default `externum run` path (transpile to Python) executes everything correctly, which is
what the tables above measure.

## Reproduce

```bash
pip install hyperfine
git clone https://github.com/BartoszOsiej/externum && cd externum
pip install .
hyperfine -w 2 -m 8 \
  "externum run benchmarks/bench.ext" \
  "python3 benchmarks/bench.py" \
  "bash benchmarks/bench.sh"
```
