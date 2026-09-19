## Architecture

externum is a **triple-target programming language** — same source compiles to Python, Bash, or a native binary. 366 tests, all three targets.

### Compiler Pipeline

```mermaid
graph LR
    A["Source Code<br/>.ext file"] --> B["Lexer<br/>Token stream"]
    B --> C["Parser<br/>Pratt + precedence"]
    C --> D["Typed AST<br/>Low-level IR"]
    D --> E{"Target<br/>Selector"}
    E -->|"--target python"| F["Python Emitter<br/>AST → .py"]
    E -->|"--target bash"| G["Bash Emitter<br/>AST → .sh"]
    E -->|"--target native"| H["Native Emitter<br/>AST → ELF binary"]
    F --> I["python3 -c<br/>Execution"]
    G --> J["bash -n + exec<br/>Execution"]
    H --> K["Direct exec<br/>ELF binary"]

    style E fill:#F15A24,color:#000,stroke:none
    style G fill:#DA2C38,color:#fff,stroke:none
```

### Test Matrix

```mermaid
flowchart TB
    SRC["192 Test Cases"] --> PY["Python Target<br/>python3 -c check"]
    SRC --> BA["Bash Target<br/>bash -n + run"]
    SRC --> NA["Native Target<br/>Binary execution"]
    PY --> PASS{"All 3 pass?"}
    BA --> PASS
    NA --> PASS
    PASS -->|"Yes"| OK["✅ CI Green"]
    PASS -->|"No"| FAIL["❌ CI Red<br/>+ diff output"]
```

## Quickstart

### One-liner — Install & compile

```bash
pip install externum && echo 'fn main() { print("hello") }' > hello.ext && externum compile --target python hello.ext && python3 hello.py
```

### One-liner — Build from source

```bash
git clone https://github.com/BartoszOsiej/externum && cd externum && pip install -e ".[dev]" && pytest -q
```

### One-liner — Triple-compile demo

```bash
git clone https://github.com/BartoszOsiej/externum && cd externum && \
  externum compile --target python examples/hello.ext -o hello.py && \
  externum compile --target bash examples/hello.ext -o hello.sh && \
  externum compile --target native examples/hello.ext -o hello && \
  python3 hello.py && bash hello.sh && ./hello
```

### One-liner — Run full test suite

```bash
git clone https://github.com/BartoszOsiej/externum && cd externum && pip install -e ".[dev]" && pytest tests/ -v --tb=short
```

### One-liner — Docker (all three targets)

```bash
docker run --rm -v "$(pwd)":/src -w /src \
  ghcr.io/bartoszosiej/externum:latest \
  bash -c "externum compile --target python hello.ext -o /src/hello.py && externum compile --target bash hello.ext -o /src/hello.sh && externum compile --target native hello.ext -o /src/hello"
```
