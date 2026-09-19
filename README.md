<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=130&section=header&text=externum&fontSize=32&animation=fadeIn" width="100%" />

<div align="center">

[![Typing SVG](https://readme-typing-svg.demolab.com/?font=JetBrains+Mono&weight=600&size=18&duration=3000&pause=1200&color=58A6FF&center=true&vCenter=true&width=600&height=45&lines=Programming%20language%20%E2%80%94%20compiles%20to%20Python%2C%20Bash%2C%20binary.%20379%20tests%2C%20browser%20REPL%2C%20DRM%2C%20ownership%2Btraits%20)](https://github.com/BartoszOsiej/externum)

</div># ⚡ Externum

![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)
![PyPI](https://img.shields.io/badge/PyPI-externum%402.0.0-3776AB?style=flat-square&logo=pypi)
![Tests](https://img.shields.io/badge/Tests-379%20✓-brightgreen?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](https://github.com/BartoszOsiej/externum/blob/main/LICENSE)

**A self-hosted programming language blending Python readability, binary performance,
and Bash system control. The compiler is written in Externum itself — bootstrap with a minimal Python runtime.**

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

> 🇵🇱 [Wersja polska](README.pl.md) · [Documentation](https://bartoszosiej.github.io/Docs/projects/externum/) · [Language Spec](docs/WIKI.md) · [![Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/BartoszOsiej/externum)

<p align="center">
  <a href="https://bartoszosiej.github.io/externum/"><b>▶ Try in your browser — no install</b></a>
</p>

<p align="center">
  <img src="assets/repl.gif" alt="Externum REPL — live in the terminal" width="49%">
  <img src="assets/compile.gif" alt="Compiling Externum to Python, Bash and a standalone binary" width="49%">
</p>


---

## Why?

Most languages force you to choose: **readable or fast, scripting or systems**.
Externum is one language for all three targets — write readable Python-style
code, keep inline Bash for system control, and compile to a standalone artifact
when you need to ship. Self-hosted: the compiler is written in Externum itself.

```text
$ externum run demo.ext
hello world from Externum
Linux 7.2.4-arch1-2

$ externum demo.ext --target python -o demo.py
Output written to demo.py

$ python3 demo.py        # pure Python — runs without Externum
hello world from Externum
Linux 7.2.4-arch1-2
```

*(source: `demo.ext` — typed variable, `$"…"` interpolation, inline `` `uname -sr` ``)*

---

🌐 **[▶ Try Externum in your browser — no install](https://bartoszosiej.github.io/externum/)** · or `pip install externum`

---

## Table of Contents

- [What it can do](#what-it-can-do)
- [Installation](#installation)
- [Usage](#usage)
- [Example](#example)
- [Browser Playground & Bot](#browser-playground--bot)
- [Standard Library](#standard-library)
- [DRM System](#drm-system)
- [Project Structure](#project-structure)
- [Tests](#tests)
- [Docker](#docker)
- [Benchmarks](#benchmarks)
- [License](#license)

---

## What it can do

| Area | Support |
|---|---|
| **Data types** | lists, dicts, tuples, sets, f-strings, `$"…"` interpolation, binary `0b` and hex `0x` literals |
| **Control flow** | `if/elif/else`, `while`, `for ... in`, `break`, `continue`, `try/except/else/finally`, `with`, `assert` |
| **Functions** | default parameters, `*args`/`**kwargs`, type annotations, recursion, lambdas, closures, generators (`yield`) |
| **OOP** | classes, inheritance, methods, `self`, attributes |
| **Modules** | `import`/`from ... import`, custom `.ext` modules, standard library |
| **Expressions** | full operator precedence, chained comparisons, bitwise, ternaries, comprehensions, tuple unpacking |
| **Shell** | inline bash `` `cmd` `` and `%% ... %%` blocks |
| **Tooling** | REPL, compilation to 3 targets, `argv`, TUI IDE |

---

## Installation

```bash
pip install externum        # PyPI
externum --version          # Externum 4.1.0

# From source
git clone https://github.com/BartoszOsiej/externum.git
cd externum
pip install -e .
```

---

## Usage

```bash
# Run a program
externum run examples/pokedex.ext

# TUI IDE (written in Externum itself)
externum ide
externum ide myprogram.ext

# REPL
externum repl

# Compile to a runnable .exbc artifact (no source needed to run it)
externum examples/hello.ext --target bytecode -o hello.exbc
externum run hello.exbc

# Compile to all targets
externum examples/hello.ext

# Compile to Python / Bash
externum examples/hello.ext --target python -o hello.py
externum examples/hello.ext --target bash   # real bash: loops, arithmetic, if/for/while, print
```

### What's new in v4.2

- **`|>` pipeline operator** — `x |> f(a, b)` means `f(x, a, b)`; works in the Python target
  and on the VM (chaining works because precedence binds left: `x |> f |> g` is `g(f(x))`)
- **`fn` keyword** — `fn name(args) -> T:` is now an alias for `def` (Rust-flavored spelling)
- **Real bash target** — `--target bash` translates module-level Externum logic (arithmetic,
  `while`/`for range`, `if/elif/else`, `print`, embedded `bash { ... }` blocks verbatim) into a
  standalone `set -euo pipefail` script. **Functions too** (v4.2.1): `def`/`fn` become real bash
  functions — `local` params, defaults, recursion, string concatenation; `return` values are
  captured via `$( )`. Unsupported statements emit **warnings** — the target never silently
  produces an empty script again
- **VM bugfixes** — augmented assignment at module top level no longer silently discards the
  write (infinite loops, [#21](https://github.com/BartoszOsiej/externum/issues/21)); parenthesized
  right-hand sides no longer raise `undefined global` ([#22](https://github.com/BartoszOsiej/externum/issues/22));
  `%=`, `&=`, `|=`, `^=`, `<<=`, `>>=` lex correctly; `PIPE_CALL` dispatches user functions

---

## Example


### String interpolation — `$"…"`

```rust
name: Any = "Bartosz"
print($"Hello {name}, 2+2 = {2+2}!")   // → Hello Bartosz, 2+2 = 4!
print($"{{literal}}")                    // → {literal}
```

`$"…"` strings interpolate `{expr}` at runtime — arithmetic, calls and any
variable in scope. The Python target emits native f-strings; the bytecode VM
concatenates parts with the `str` intrinsic. Same semantics on every target.

`examples/pokedex.ext` uses classes with inheritance, comprehensions,
lambdas, exceptions, generators, f-strings, and the standard library:

```python
import mathx
import strings

class Fire(Pokemon):
    def __init__(self, name, hp=50):
        Pokemon.__init__(self, name, ["fire"], hp)

fire_team = [p.name for p in squad if p.is_type("fire")]
weakest = min(squad, key=lambda p: p.hp)
nums = [f for f in fibonacci(10) if f % 2 == 0]
```

---

## Demos

> 🎬 VHS-powered TUI recordings — rendered in CI, auto-committed as GIFs.

| Demo | Preview |
|------|---------|
| **REPL** | ![REPL](assets/repl.gif) |
| **Compile** | ![Compile](assets/compile.gif) |

---

## Browser Playground & Bot

### 🌐 Live Playground

Try Externum **in your browser** — zero install, zero server. The transpiler
runs inside [Pyodide](https://pyodide.org/) (Python compiled to WASM):

```bash
# Open in Codespaces and run:
externum repl

# Or open the browser playground:
https://bartoszosiej.github.io/externum/
```

| What works | What doesn't (browser sandbox) |
|---|---|
| Full REPL with custom functions | Shell `` `cmd` `` and `%% ... %%` blocks |
| Classes, lambdas, comprehensions | File I/O (sandboxed filesystem) |
| Stdlib: mathx, strings, structs | Binary compilation (Python target only) |

### 🤖 Issue-Command Bot

Extend Externum from GitHub Issues — no local setup needed:

| Command | What it does | Example |
|---|---|---|
| `/run <code>` | Execute Externum code in CI | `/run print(2 + 2)` |
| `/define <name> <body>` | Add a new stdlib function via PR | `/define clamp(x, lo, hi) if x < lo: return lo ...` |

The bot parses Issue comments, generates a PR with the new function + tests,
and runs the full test suite before merge. Language evolves through
community contributions.

---

## Standard Library

| Module | Contents |
|---|---|
| `structs` | `Stack`, `Queue`, `Counter` |
| `strings` | `reverse`, `is_palindrome`, `slugify`, `word_count`, `capitalize`, `truncate` |
| `mathx` | `clamp`, `is_even`, `gcd`, `fib`, `factorial`, `sum_of_digits` |
| `fs` | `read_file`, `write_file`, `append_file`, `file_exists`, `list_dir` |
| `jsonx` | `load`, `load_str`, `dump`, `dump_str` — JSON read/write |
| `net` | `http_get`, `http_get_status` — HTTP GET with timeout |
| `drm` | `make_license`, `verify_license`, `sign`, `verify`, `watermark` |

---

## DRM System

Every protected build carries the full defense-in-depth stack:

1. **License keys** — HMAC-SHA256 signed; `externum keygen` issues keys
2. **Watermark** — author/app/build/source-hash header in every file
3. **Tamper detection** — source SHA-256 + artifact self-hash embedded
4. **Obfuscation** — string literals encoded through a runtime helper

```bash
externum compile app.ext --protect --app-id game --author buffy --secret s3cret
EXTERNUM_LICENSE=<key> externum run app.ext --protect --app-id game --author buffy --secret s3cret
```

---

## Project Structure

```
externum/
├── lexer.py          # Tokenization (bracket-aware, bash, f-strings)
├── parser.py         # Full grammar → AST
├── bytecode.py       # Bytecode compiler (EXBC format) + .exbc artifact I/O
├── compiler.py       # Python/Bash transpiler
├── vm.py             # Bytecode virtual machine
├── typesys.py        # Static type checker
├── drm.py            # DRM: license, watermark, tamper-detection
├── runtime/          # Runtime: exec, import .ext, REPL
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standard library (.ext)
tools/                # Tooling in Externum
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 379 unit tests
docs/WIKI.md          # Language specification
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v   # 379 tests
```

---

## Docker

```bash
# Build
docker build -t externum .

# Run
docker run --rm externum run examples/hello.ext

# REPL
docker run -it externum repl
```

---


## Benchmarks

Measured on Intel i7-4610M (3.00 GHz), Arch Linux, CPython 3.14.7 —
median of 30 runs (`examples/hello.ext`, typed bindings + inline Bash):

| Scenario | Time |
|---|---|
| `externum compile` (.ext → Python target) | **78 ms** |
| `externum run` (lex + parse + compile + exec) | **95 ms** |
| `bin/externum run` (6 KB bootstrap, self-hosted path) | **63 ms** |
| Running the compiled `.py` directly | **36 ms** |

### CPU-bound loop (2M iterations of `(i*3+7) % 1000`) — [methodology](benchmarks/README.md)

| Command | Mean | vs. Externum |
|---|---|---|
| `externum run` (lex → parse → transpile → exec) | **551 ms ± 42** | 1.00× |
| compiled artifact executed directly | **458 ms** | 1.20× faster |
| plain Python (idiomatic `for range`) | **340 ms ± 10** | 1.62× faster |
| Bash (`$(( ))` arithmetic loop, no forks) | **6.16 s ± 0.06** | **11.2× slower** |

Identical output verified for all three before timing. Full methodology, cold-start numbers
and repro in [benchmarks/README.md](benchmarks/README.md).

| Artifact | Size |
|---|---|
| `hello.ext` source | 177 B |
| Compiled `hello.py` | 161 B |
| `bin/externum` bootstrap (the only Python needed) | 6.4 KB |

The full toolchain — lexer, parser, bytecode compiler, VM and runtime —
bootstraps from a 6.4 KB Python stub; everything else is written in Externum.

---

## License

MIT
## Deep Dives

Extended dossiers (architecture, verification, benchmarks, error codex) ship in this repo:
- [docs/ERROR_CODEX.md](docs/ERROR_CODEX.md)
- [SECURITY.md](SECURITY.md)
