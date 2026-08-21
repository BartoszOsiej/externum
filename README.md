<img src="https://capsule-render.vercel.app/api?type=rect&color=0:0d1117,50:0969da,100:f0883e&height=140&section=header&text=Externum&fontSize=38&fontColor=fff&desc=a%20programming%20language%20from%20scratch%20%C2%B7%20one%20source%2C%20three%20targets&descSize=15&descAlignY=72" width="100%" />


[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/BartoszOsiej/externum/badge)](https://scorecard.dev/viewer/?uri=github.com/BartoszOsiej/externum)

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/externum?style=for-the-badge&logo=pypi)](https://pypi.org/project/externum/)
[![GHCR](https://img.shields.io/badge/GHCR-image-2496ED?style=for-the-badge&logo=docker)](https://github.com/BartoszOsiej/externum/pkgs/container/externum)
[![Release](https://img.shields.io/badge/release-artifacts-8A2BE2?style=for-the-badge&logo=github)](https://github.com/BartoszOsiej/externum/releases)
[![Tests](https://img.shields.io/badge/tests-192%20passing-2ea043?style=for-the-badge&logo=githubactions)](https://github.com/BartoszOsiej/externum/actions)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)

**Externum v3.0** — a full programming language blending Python readability,
binary performance, and Bash system control.

</div>

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

A single source compiles to **Python**, **Bash**, and a **binary**
representation — or runs directly.

## What it can do (v3)

| Area | Support |
|---|---|
| **Data types** | lists, dicts, tuples, sets (also multiline), f-strings, binary `0b` and hex `0x` literals |
| **Control flow** | `if/elif/else`, `while`, `for ... in` (multi-variable), `break`, `continue`, `try/except/else/finally`, `with`, `assert` |
| **Functions** | default parameters, `*args`/`**kwargs`, type annotations, recursion, lambdas, closures, generators (`yield`) |
| **OOP** | classes, inheritance, methods, `self`, attributes |
| **Modules** | `import`/`from ... import`, custom `.ext` modules (loader), standard library |
| **Expressions** | full operator precedence, chained comparisons, bitwise ops, ternaries, comprehensions, tuple unpacking |
| **Shell** | inline bash `` `cmd` `` and `%% ... %%` blocks |
| **Tooling** | REPL, compilation to 3 targets, `argv` |

## Installation

```bash
pip install externum    # or: pip install -e .
externum --version      # Externum 3.0.0
```

## Usage

```bash
externum run examples/pokedex.ext              # run a program
externum repl                                  # REPL
externum examples/hello.ext                    # compile to all targets
externum examples/hello.ext --target python -o hello.py
externum examples/hello.ext --target bash
```

<details>
<summary><b>🧩 Example — pokedex.ext</b></summary>

Uses classes with inheritance, comprehensions, lambdas, exceptions,
generators, f-strings, and the standard library:

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

Standard library (written in Externum):

| Module | Contents |
|---|---|
| `structs` | `Stack`, `Queue`, `Counter` |
| `strings` | `reverse`, `is_palindrome`, `slugify`, `word_count`, `capitalize`, `truncate` |
| `mathx` | `clamp`, `is_even`, `gcd`, `fib`, `factorial`, `sum_of_digits` |
| `fs` | `read_file`, `write_file`, `append_file`, `file_exists`, `list_dir` |

</details>

## 🔥 Hard Mode (`--hard`)

Run any program with `--hard` to enable the hardcore ruleset. Existing
programs that violate it fail loudly:

> [!WARNING]
> Hard Mode is **giga trudny** — manual memory management in a Python-family language.

- **Mandatory declarations** — every variable needs `x: Type` before use
- **Static typing** — assignment/return mismatches rejected at compile time (`Int` widens to `Float`)
- **Manual memory** — `alloc(Int)`, `free(p)`, `@p`; double-free and use-after-free are **compile errors** (ownership enforced)
- **`match`/`case`** — pattern matching with literals, binds, guards, destructuring
- **Traits** — `trait X:` + `impl X for Y:`; missing methods or wrong return types rejected
- **`unsafe:` blocks** — the escape hatch: checks skipped inside
- **Macros** — compile-time expansion
- **Concurrency** — `spawn(f(...))`, `chan()`, `send(ch, v)`, `recv(ch)`
- **Esoteric operators** — `≠`, `≈`, `←` work like `!=`, `==`, `=`

```bash
externum run examples/hardcore.ext --hard
```

<details>
<summary><b>🔒 DRM system (`--protect`) — license keys, watermark, tamper detection</b></summary>

Every protected build carries the full defense-in-depth stack:

1. **License keys** — HMAC-SHA256 signed; `externum keygen --app-id X --secret S` issues keys, the artifact verifies them (env `EXTERNUM_LICENSE`), never embedding the secret
2. **Watermark** — author/app/build/source-hash header in every file
3. **Tamper detection** — source SHA-256 + artifact self-hash embedded; modified copies detected
4. **Obfuscation** — string literals encoded through a runtime helper

```bash
externum compile app.ext --protect --app-id game --author buffy --secret s3cret
EXTERNUM_LICENSE=<key> externum run app.ext --protect --app-id game --author buffy --secret s3cret
```

Standard-library `drm.ext` provides `sign`/`verify`/`watermark` in-language.

</details>

<details>
<summary><b>📁 Project structure</b></summary>

```
externum/
├── lexer.py          # Tokenization (bracket-aware, bash, f-strings)
├── parser.py         # Full grammar → AST
├── compiler.py       # Codegen → Python / Bash / binary
├── typesys.py        # NV2.0 type checker (hard mode: static types, ownership)
├── hardmode.py       # NV2.0 macros + hard-mode pipeline
├── drm.py            # NV2.0 DRM: license keys, watermark, tamper-detection
├── runtime/          # Runtime: exec, import .ext, REPL (+ rtlib helpers)
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standard library (.ext) — incl. drm.ext
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 192 tests
WIKI.md               # Language specification
```

</details>

## Tests

```bash
python3 -m unittest discover -s tests -v   # 192 tests
```

> [!NOTE]
> Modules reserved in the API (`externum.llm`, `neural`, `distributed`,
> `types`, `spec`, `debug`) remain planned — the package works without them.

---

<div align="center">

**Part of [BartoszOsiej](https://github.com/BartoszOsiej)'s systems toolkit** · [`halcyon`](https://github.com/BartoszOsiej/halcyon-process-monitor) · [`cybersec-tools`](https://github.com/BartoszOsiej/cybersec-tools)

MIT © 2026 Bartosz Osiej

</div>
