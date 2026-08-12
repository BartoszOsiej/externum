# Externum Language — Specification (v3.0)

## Introduction

**Externum** is a programming language that fuses Python's readability,
binary performance and Bash's system control into one unified paradigm:

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

One source (`.ext`) compiles to **Python**, **Bash** and **binary** targets
simultaneously, or executes directly (`externum run`). The implementation is
pure Python 3.10+ with zero external dependencies.

## Toolchain

| Component | File | Role |
|---|---|---|
| Lexer | `externum/lexer.py` | Tokenization (bracket-aware, bash, f-strings) |
| Parser | `externum/parser.py` | Full grammar → AST |
| Compiler | `externum/compiler.py` | Codegen → Python / Bash / binary |
| Runtime | `externum/runtime/` | Execution, `.ext` module loader, REPL |
| CLI | `externum/__main__.py` | `run`, `repl`, `compile` |

## Language features

### Types & literals

- Numbers: `42`, `3.14`, binary `0b1010`, hex `0xFF`
- Strings: `"..."`, `'...'`, triple-quoted `"""..."""`, f-strings `f"{x}"`
- Collections: lists `[1, 2]`, dicts `{"a": 1}`, tuples `(1, 2)`, sets `{1, 2}`
  — all support multiline forms
- Booleans/None: `True`, `False`, `None`

### Variables & assignment

```python
x = 42
x += 1
a, b = 1, 2          # tuple unpacking
d["k"] = "v"         # index assignment
obj.attr = 5         # attribute assignment
```

### Operators (Python precedence)

Arithmetic `+ - * / % // **`, comparisons `== != < > <= >= is in`,
logical `and or not` (also `&& ||`), bitwise `& | ^ ~ << >>`,
ternary `a if cond else b`.

### Control flow

```python
if x > 10:
    ...
elif x > 0:
    ...
else:
    ...

while i < 10:
    i += 1

for i in range(10):
    print(i)

for i, v in enumerate(items):   # multiple targets
    print(i, v)
```

### Functions

```python
def add(a, b):
    return a + b

def greet(name, greeting="hi", *args, **kwargs):
    print(greeting, name)

f = lambda x, y: x + y          # lambdas
add5 = make_adder(5)            # closures
def gen():
    yield 1                     # generators
```

### Classes

```python
class Animal:
    def __init__(self, name):
        self.name = name
    def speak(self):
        print(self.name)

class Dog(Animal):              # inheritance
    def speak(self):
        print("woof " + self.name)
```

### Errors

```python
try:
    x = 1 / 0
except ZeroDivisionError as e:
    print("caught", e)
else:
    print("ok")
finally:
    print("done")

raise ValueError("boom")
assert x > 0
```

### Modules & stdlib

```python
import mathx
import strings
from structs import Stack

import os          # python stdlib also available
```

Standard library (written in Externum, in `lib/`):
`structs` (Stack, Queue, Counter), `strings`, `mathx`, `fs`.

### Bash integration

```python
`ls -la`            # inline bash
%%
echo "block"        # bash block
%%
```

### Comprehensions

```python
evens = [i for i in range(10) if i % 2 == 0]
caps = {n: n.upper() for n in names}
```

## CLI

```
externum run program.ext [args...]   # execute
externum repl                        # interactive shell
externum program.ext --target python|bash|binary|all
externum program.ext -o out.py
externum --version                   # Externum 3.0.0
```

## Compilation pipeline

```
source (.ext) → Lexer → tokens → Parser → AST → Compiler → python/bash/binary
                                                ↘ Runtime (exec) / REPL
```

1. **Lexical analysis** — tokens with INDENT/DEDENT (bracket-aware),
   binary/hex literals, strings + f-strings, operators, bash constructs.
2. **Parsing** — recursive descent with operator precedence, full statement
   grammar (functions, classes, try/except, imports, with, comprehensions).
3. **Code generation** — Python (with `subprocess.run` for bash), Bash
   (extracted commands), binary (collected bit literals).
4. **Runtime** — in-process exec of generated Python; meta-path finder loads
   `.ext` modules; REPL with block-completion detection.

## Tests

`python3 -m unittest discover -s tests` — 118 tests covering lexer, parser,
compiler and runtime (classes, exceptions, imports, lambdas, comprehensions,
generators, stdlib, REPL).

## License

MIT License — see LICENSE file for details.
