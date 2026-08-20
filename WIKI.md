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
| Type checker | `externum/typesys.py` | Hard-mode static types + ownership analysis |
| Hard mode | `externum/hardmode.py` | Macros, mandatory-declaration pipeline |
| DRM | `externum/drm.py` | License keys, watermark, tamper-detection, obfuscation |
| Runtime | `externum/runtime/` | Execution, `.ext` module loader, REPL, memory/concurrency helpers (`rtlib.py`) |
| CLI | `externum/__main__.py` | `run`, `repl`, `compile`, `keygen` |

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
`structs` (Stack, Queue, Counter), `strings`, `mathx`, `fs`, `jsonx`
(JSON load/dump), `net` (HTTP GET), `drm` (license keys, watermark,
file/binary integrity).

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

# NV2.0 — hard mode
externum run program.ext --hard

# NV2.0 — DRM
externum compile program.ext --protect --app-id X --author Y --secret S
externum keygen --app-id X --author Y --secret S    # issue a license key
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

`python3 -m unittest discover -s tests` — **192 tests** covering lexer,
parser, compiler and runtime (classes, exceptions, imports, lambdas,
comprehensions, generators, stdlib, REPL), plus the NV2.0 suites:
`tests/test_drm.py` (license keys, watermark, tamper-detection,
obfuscation, runtime guard, unified key format, `drm.ext`, `keygen.ext`,
`egs_manifest.ext`, CLI) and the stdlib suites (`jsonx`, `net`).

## License

MIT License — see LICENSE file for details.

## NV2.0 — Hard Mode (`externum run --hard` / `compile --hard`)

The hardcore ruleset turns Externum into a genuinely difficult language:

- **Declarations are mandatory.** `x = 5` is a compile error; write
  `x: Int = 5`. Types: `Int, Float, Str, Bool, Void, Any, Ptr[T], List[T],
  Dict[K, V], Optional[T]`.
- **Static typing.** `x: Int = 'nope'` fails; `Int` widens to `Float`;
  function `-> Type` return types are enforced against `return` statements.
- **Ownership.** `p: Ptr[Int] = alloc(Int)`; read/write via `@p`; `free(p)`
  exactly once. Double-free, use-after-free, deref of a non-pointer and
  `free()` of a non-pointer are **compile errors** (see `externum/typesys.py`).
  `unsafe:` blocks skip all checks.
- **Pattern matching.** `match x:` + `case` with literals, binds, guards
  (`case n if n > 3:`), `[a, b]` / `(a, b)` destructuring, `_` wildcard.
- **Traits.** `trait Speaker:` declares method stubs; `impl Speaker for Dog:`
  must implement all of them with matching return types — else compile error.
- **Macros.** `macro SQ(x) { (x) * (x) }` expands textually before parsing.
- **Concurrency.** `ch = chan()`, `spawn(worker(ch))`, `send(ch, v)`,
  `recv(ch)` (thread-backed).
- **Esoteric operators.** `≈` (eq), `≠` (neq), `←` (assign).

### Example
```python
p: Ptr[Int] = alloc(Int)
@p = 42
print(@p)     # 42
free(p)       # double-free or @p after this line = compile error
```

## NV2.0 — DRM (`externum compile --protect`)

`--protect` wraps every output with the full stack (`externum/drm.py`):

1. **License** — `externum keygen --app-id X --author Y --secret S` issues
   HMAC-SHA256 signed keys (`app_id:author:expires:sig`, base64). The
   artifact stores only the *expected digest* — the secret never ships. At
   runtime `EXTERNUM_LICENSE=<key>` is verified; a wrong key raises
   `Externum DRM: invalid license key`.
2. **Watermark** — header with app_id, author, build id and the source
   SHA-256; a runtime-readable marker (`Externum::DRM::app::author`).
3. **Tamper detection** — source hash + artifact self-hash embedded and
   re-verified at startup.
4. **Obfuscation** — string literals are base64-encoded and decoded through
   an injected `_ext_s()` helper.

Standard library `lib/drm.ext` exposes `make_license`, `verify_license`,
`sign`, `verify`, `watermark` in Externum itself — using the **exact same
base64 key format** as the CLI `externum keygen`, so keys issued in Python
verify in Externum and vice versa. `tools/keygen.ext` issues keys
entirely from Externum.
