# Externum

**Externum v3.0** — a full programming language blending Python readability,
binary performance, and Bash system control. A single source compiles to
**Python**, **Bash**, and a **binary** representation — or runs directly.

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

## What it can do (v3)

| Area | Support |
|---|---|
| **Data types** | lists, dicts, tuples, sets (also multiline), f-strings, binary `0b` and hex `0x` literals |
| **Control flow** | `if/elif/else`, `while`, `for ... in` (multi-variable), `break`, `continue`, `try/except/else/finally`, `with`, `assert` |
| **Functions** | default parameters, `*args`/`**kwargs`, type annotations (optional), recursion, lambdas, closures, generators (`yield`) |
| **OOP** | classes, inheritance, methods, `self`, attributes |
| **Modules** | `import`/`from ... import`, custom `.ext` modules (loader), standard library |
| **Expressions** | full operator precedence, chained comparisons, bitwise `& \| ^ ~ << >>`, ternaries, comprehensions (list/dict), tuple unpacking |
| **Shell** | inline bash `` `cmd` `` and `%% ... %%` blocks |
| **Tooling** | REPL, compilation to 3 targets, `argv` |

## Installation

```bash
pip install -e .        # Python 3.10+
externum --version      # Externum 3.0.0
```

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

## Example (pokedex)

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

## Standard library (written in Externum)

| Module | Contents |
|---|---|
| `structs` | `Stack`, `Queue`, `Counter` |
| `strings` | `reverse`, `is_palindrome`, `slugify`, `word_count`, `capitalize`, `truncate` |
| `mathx` | `clamp`, `is_even`, `gcd`, `fib`, `factorial`, `sum_of_digits` |
| `fs` | `read_file`, `write_file`, `append_file`, `file_exists`, `list_dir` |

```bash
externum run examples/pokedex.ext
```

## Project structure

```
externum/
├── lexer.py          # Tokenization (bracket-aware, bash, f-strings)
├── parser.py         # Full grammar → AST
├── compiler.py       # Codegen → Python / Bash / binary
├── typesys.py        # NV2.0 type checker (hard mode: static types, ownership)
├── hardmode.py       # NV2.0 macros + hard-mode pipeline
├── drm.py            # NV2.0 DRM: license keys, watermark, tamper-detection, obfuscation
├── runtime/          # Runtime: exec, import .ext, REPL (+ rtlib.py memory/concurrency helpers)
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standard library (.ext) — incl. drm.ext
lib/drm.ext           # NV2.0 DRM stdlib: sign / verify / watermark in Externum
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 167 unit tests
WIKI.md               # Language specification
```

## NV2.0 — Hard Mode (`--hard`) — giga trudny

Run any program with `externum run program.ext --hard` (or `compile … --hard`)
to enable the hardcore ruleset. Existing programs that violate it fail loudly:

- **Mandatory declarations** — every variable needs `x: Type` before use;
  using an undeclared name is a compile error.
- **Static typing** — assignment/return mismatches are rejected at compile
  time (`Int` widens to `Float`; everything else must match).
- **Manual memory** — `alloc(Int)`, `free(p)`, `@p` dereference; double-free
  and use-after-free are **compile errors** (ownership is enforced).
- **`match`/`case`** — pattern matching with literals, binds, guards, and
  list/tuple destructuring.
- **Traits** — `trait X:` + `impl X for Y:`; implementations missing
  methods or with wrong return types are rejected.
- **`unsafe:` blocks** — the escape hatch: checks are skipped inside.
- **Macros** — `macro NAME(a, b) { … }` compile-time expansion.
- **Concurrency** — `spawn(f(...))`, `chan()`, `send(ch, v)`, `recv(ch)`.
- **Esoteric operators** — `≠`, `≈`, `←` work like `!=`, `==`, `=`.

```bash
externum run examples/hardcore.ext --hard
```

## NV2.0 — DRM (`--protect`) — obfuskacja, watermark, licencja

Every protected build carries the full defense-in-depth stack:

1. **License keys** — HMAC-SHA256 signed; `externum keygen --app-id X
   --secret S` issues keys, the artifact verifies them (env
   `EXTERNUM_LICENSE`), never embedding the secret.
2. **Watermark** — author/app/build/source-hash header in every file.
3. **Tamper detection** — source SHA-256 + artifact self-hash embedded;
   modified copies are detected.
4. **Obfuscation** — string literals encoded through a runtime helper.

```bash
externum compile app.ext --protect --app-id game --author buffy --secret s3cret
EXTERNUM_LICENSE=<key> externum run app.ext --protect --app-id game --author buffy --secret s3cret
```

Standard-library `drm.ext` provides `sign`/`verify`/`watermark` in-language.

## Tests

```bash
python3 -m unittest discover -s tests -v   # 167 tests
```

## Roadmap

Modules reserved in the API (`externum.llm`, `neural`, `distributed`,
`types`, `spec`, `debug`) remain planned — the package works without them.
