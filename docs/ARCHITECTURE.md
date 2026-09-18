# Externum Architecture

## Overview

Externum is a general-purpose programming language with its own lexer, parser, bytecode compiler, and virtual machine. It supports both a **Python transpiler** backend (for rapid development) and a **native bytecode VM** backend (for performance).

## Compilation Pipeline

```
Source Code (.ext)
       │
       ▼
┌─────────────┐
│    Lexer     │  Tokenization (keywords, strings, numbers, operators)
│  lexer.rs   │
└──────┬──────┘
       │ Vec<Token>
       ▼
┌─────────────┐
│    Parser    │  Recursive descent with precedence climbing
│  parser.rs  │  → AST (Abstract Syntax Tree)
└──────┬──────┘
       │ Vec<ASTNode>
       ▼
┌─────────────┐
│  Preprocessor│  Macro expansion, import resolution
│ analysis.rs │
└──────┬──────┘
       │ Vec<ASTNode>
       ▼
┌─────────────────────────────────────────┐
│              Backend Switch              │
├───────────────────┬─────────────────────┤
│                   │                     │
│  Python Backend   │  Bytecode Backend   │
│  runtime/         │  bytecode.rs        │
│  Transpile AST →  │  Compile AST →      │
│  Python source    │  EXBC bytecode      │
│       │           │       │             │
│       ▼           │       ▼             │
│  exec() Python    │  VM (vm.rs)         │
│                   │  Execute bytecode   │
└───────────────────┴─────────────────────┘
```

## Module Structure

```
externum/
├── src/
│   ├── lib.rs           # Library root
│   ├── main.rs          # CLI entry point (__main__.py)
│   ├── lexer.rs         # Tokenizer
│   ├── parser.rs        # Recursive descent parser
│   ├── analysis.rs      # Preprocessor (macros, imports)
│   ├── ast.rs           # AST node definitions
│   ├── bytecode.rs      # Bytecode compiler (AST → EXBC)
│   ├── vm.rs            # Virtual machine (EXBC executor)
│   ├── runtime/         # Python transpiler backend
│   │   ├── __init__.py  # Runtime class
│   │   ├── _finder.py   # Import finder
│   │   └── transpiler.py# AST → Python code generator
│   └── ide/             # TUI IDE
│       ├── __init__.py
│       ├── buffer.py    # Text buffer
│       ├── editor.py    # Editor logic
│       └── ui.py        # Terminal UI
├── lib/
│   └── compiler/        # Externum-written compiler
│       ├── types.ext
│       ├── tokens.ext
│       ├── lexer.ext
│       ├── parser.ext
│       └── compiler.ext
├── bin/
│   └── externum         # Bootstrap script (Python → Externum)
├── tests/
│   ├── test_*.py        # Unit tests (307+)
│   └── test_smoke.py    # Language feature smoke tests
└── examples/
    └── *.ext            # Example programs
```

## Key Components

### Lexer (`lexer.rs`)
- Tokenizes source into `Token` structs
- Supports: keywords, identifiers, strings (with interpolation), numbers (int/float/hex/binary/octal), operators, comments
- 50+ token types

### Parser (`parser.rs`)
- Recursive descent with precedence climbing
- Handles: expressions, statements, blocks, classes, traits, enums, pattern matching, comprehensions, f-strings, try/except, with-statement, generators, macros
- Produces structured `ASTNode` tree

### Bytecode Compiler (`bytecode.rs`)
- Compiles AST to EXBC bytecode format
- 80+ opcodes: arithmetic, jumps, closures, classes, patterns, exceptions, imports
- Supports: pipe operator `|>`, defer, generators, manual memory (`alloc`/`free`)

### Virtual Machine (`vm.rs`)
- Stack-based bytecode interpreter
- Features: closures, classes, inheritance, pattern matching, exceptions, imports
- Algebraic types: `Result`, `Option`, `Ok`, `Err`, `Some`
- Concurrency: `spawn`, `chan`, `send`, `recv`

### Python Transpiler (`runtime/`)
- Transpiles Externum AST to Python source code
- Used for rapid development and testing
- Supports all language features including comprehensions, f-strings, try/except

## Data Flow

### Compilation (Bytecode Backend)
```
Tokenize → Parse → Preprocess → Compile → Link → Execute
   │          │          │           │        │       │
   │          │          │           │        │       └─ VM runs EXBC
   │          │          │           │        └─ Constants, bytecode
   │          │          │           └─ BytecodeModule
   │          │          └─ Macros expanded, imports resolved
   │          └─ AST tree
   └─ Token stream
```

### Execution (Python Backend)
```
Tokenize → Parse → Preprocess → Transpile → exec()
   │          │          │           │          │
   │          │          │           │          └─ Python executes
   │          │          │           └─ Python source code
   │          │          └─ Macros expanded
   │          └─ AST tree
   └─ Token stream
```

## Self-Hosting

Externum has a self-hosted compiler written in Externum itself:

1. **Bootstrap** (`bin/externum`): ~200 lines of Python that sets up the VM
2. **Lexer** (`lib/compiler/lexer.ext`): Written in Externum
3. **Parser** (`lib/compiler/parser.ext`): Written in Externum
4. **Compiler** (`lib/compiler/compiler.ext`): Written in Externum

The bootstrap loads the Externum compiler, which compiles user programs to bytecode.

## Testing Strategy

- **307+ unit tests**: Lexer, parser, compiler, VM, runtime
- **29 smoke tests**: Language features (arithmetic → imports)
- **12 VM tests**: Bytecode execution
- **CI/CD**: 12-stage pipeline (lint, typecheck, tests, VM, self-hosted, integration, security, typos, build, Docker, docs, smoke)

## Performance

| Operation | Time |
|-----------|------|
| Lexer (1KB) | ~50μs |
| Parser (1KB) | ~100μs |
| Bytecode compile (1KB) | ~80μs |
| VM execute (1KB) | ~200μs |
| Python transpile (1KB) | ~150μs |
