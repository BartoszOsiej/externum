# ⚡ Externum

![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)
![PyPI](https://img.shields.io/badge/PyPI-externum%402.0.0-3776AB?style=flat-square&logo=pypi)
![Tests](https://img.shields.io/badge/Tests-192%20✓-brightgreen?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker)

**A full programming language blending Python readability, binary performance,
and Bash system control. A single source compiles to Python, Bash, and a
binary representation — or runs directly.**

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

> 🇵🇱 [Wersja polska](README.pl.md) · [Documentation](https://bartoszosiej.github.io/Docs/projects/externum/) · [Language Spec (WIKI)](WIKI.md)

---

## Table of Contents

- [What it can do](#what-it-can-do)
- [Installation](#installation)
- [Usage](#usage)
- [Example](#example)
- [Standard Library](#standard-library)
- [NV2.0 Hard Mode](#nv20-hard-mode)
- [DRM System](#drm-system)
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
| **Tooling** | REPL, compilation to 3 targets, `argv` |

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

## NV2.0 Hard Mode

Run with `externum run program.ext --hard` to enable the hardcore ruleset:

- **Mandatory declarations** — every variable needs `x: Type` before use
- **Static typing** — assignment/return mismatches rejected at compile time
- **Manual memory** — `alloc(Int)`, `free(p)`, `@p` dereference; ownership enforced
- **`match`/`case`** — pattern matching with literals, binds, guards
- **Traits** — `trait X:` + `impl X for Y:`
- **`unsafe:` blocks** — escape hatch for checks
- **Macros** — `macro NAME(a, b) { … }` compile-time expansion
- **Concurrency** — `spawn(f(...))`, `chan()`, `send(ch, v)`, `recv(ch)`
- **Esoteric operators** — `≠`, `≈`, `←`

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
├── compiler.py       # Codegen → Python / Bash / binary
├── typesys.py        # NV2.0 type checker
├── hardmode.py       # NV2.0 macros + hard-mode pipeline
├── drm.py            # NV2.0 DRM: license, watermark, tamper-detection
├── runtime/          # Runtime: exec, import .ext, REPL
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standard library (.ext)
tools/                # NV-2.0 tooling in Externum
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 192 unit tests
WIKI.md               # Language specification
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v   # 192 tests
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

## License

MIT

---

> 🤖 Generated with [Codebuff](https://codebuff.com) · [Portfolio](https://bartoszosiej.github.io/Portfolio/)
