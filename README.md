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

## Tests

```bash
python3 -m unittest discover -s tests -v   # 118 tests
```

## Project structure

```
externum/
├── lexer.py          # Tokenization (bracket-aware, bash, f-strings)
├── parser.py         # Full grammar → AST
├── compiler.py       # Codegen → Python / Bash / binary
├── runtime/          # Runtime: exec, import .ext, REPL
└── __main__.py       # CLI (run / repl / compile)
lib/                  # Standard library (.ext)
examples/             # hello, calc, pokedex
tests/                # 118 unit tests
WIKI.md               # Language specification
```

## Roadmap

Modules reserved in the API (`externum.llm`, `neural`, `distributed`,
`types`, `spec`, `debug`) remain planned — the package works without them.
