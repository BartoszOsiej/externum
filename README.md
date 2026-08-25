<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=130&section=header&text=externum&fontSize=32&animation=fadeIn" width="100%" />

<div align="center">

[![Typing SVG](https://readme-typing-svg.demolab.com/?font=JetBrains+Mono&weight=600&size=18&duration=3000&pause=1200&color=58A6FF&center=true&vCenter=true&width=600&height=45&lines=Programming%20language%20%E2%80%94%20compiles%20to%20Python%2C%20Bash%2C%20binary.%20192%20tests%2C%20browser%20REPL%2C%20DRM%2C%20ownership%2Btraits%20)](https://github.com/BartoszOsiej/externum)

</div># ⚡ Externum

![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)
![PyPI](https://img.shields.io/badge/PyPI-externum%402.0.0-3776AB?style=flat-square&logo=pypi)
![Tests](https://img.shields.io/badge/Tests-307%20✓-brightgreen?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](https://github.com/BartoszOsiej/externum/blob/main/LICENSE)

**A self-hosted programming language blending Python readability, binary performance,
and Bash system control. The compiler is written in Externum itself — bootstrap with a minimal Python runtime.**

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

> 🇵🇱 [Wersja polska](README.pl.md) · [Documentation](https://bartoszosiej.github.io/Docs/projects/externum/) · [Language Spec (WIKI)](WIKI.md) · [![Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/BartoszOsiej/externum)

---

## Table of Contents

- [What it can do](#what-it-can-do)
- [Installation](#installation)
- [Usage](#usage)
- [Example](#example)
- [Browser Playground & Bot](#browser-playground--bot)
- [Standard Library](#standard-library)
- [DRM System](#drm-system)
- [Verify](#verify)
- [Project Structure](#project-structure)
- [Tests](#tests)
- [Docker](#docker)
- [License](#license)

---

## What it can do

| Area | Support |
|---|---|
| **Data types** | lists, dicts, tuples, sets, f-strings, binary `0b` and hex `0x` literals |
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
externum --version          # Externum 3.0.0

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

# Compile to all targets
externum examples/hello.ext

# Compile to Python / Bash
externum examples/hello.ext --target python -o hello.py
externum examples/hello.ext --target bash
```

---

## Example


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
├── bytecode.py       # Bytecode compiler (EXBC format)
├── compiler.py       # Python/Bash transpiler
├── vm.py             # Bytecode virtual machine
├── typesys.py        # Static type checker
├── drm.py            # DRM: license, watermark, tamper-detection
├── runtime/          # Runtime: exec, import .ext, REPL
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standard library (.ext)
tools/                # Tooling in Externum
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 307 unit tests
WIKI.md               # Language specification
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v   # 307 tests
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

## Verify

One-click verification of cosign signatures, SLSA attestation, and SBOM
for any release artifact:

```bash
curl -sL https://raw.githubusercontent.com/BartoszOsiej/externum/main/verify.sh | bash
# or
./verify.sh
```

---

## Why?

Because most languages force you to choose: readable or fast, scripting or systems, batteries or minimal. Externum lets you write once and deploy everywhere — from a Python notebook to a Bash script to a compiled binary. The browser playground means anyone can try it in 5 seconds. The issue-command bot means the community shapes the language.

---

## License

MIT