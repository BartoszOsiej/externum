# Changelog

All notable changes to Externum will be documented in this file.

## [4.2.0] - 2026-09-19

### Added
- **`|>` pipeline operator**: `x |> f(a, b)` desugars to `f(x, a, b)`. Works in the
  Python target (transpiler desugar) and on the VM (`PIPE_CALL` now dispatches
  user functions and closures, not just callables). Left-associative, so
  `x |> f |> g` chains correctly.
- **`fn` keyword**: `fn name(args) -> T:` is an alias for `def` (lexer keyword +
  parser dispatch). Rust-flavored spelling of the same construct.
- **Real bash backend** (`externum/bash_backend.py`): `--target bash` now
  translates module-level Externum logic — integer/float-free arithmetic via
  `$(( ))`, `while`, `for`/`for range`, `if`/`elif`/`else` (including `[[ str == str ]]`),
  `break`/`continue`, `print`, and embedded `bash { ... }` blocks verbatim — into a
  standalone `set -euo pipefail` script. Unsupported statements emit warnings on
  stderr instead of silently vanishing (the old behavior produced empty scripts).
- 8 new tests (VM aug-assign at module level and inside functions, operator
  semantics for `-=`/`*=`/`%=`, parenthesized RHS, pipe in both backends,
  `fn` alias, bash backend loop + warning behavior). Suite: 376.

### Fixed
- **Issue #21** — augmented assignment at module top level stored into a local
  frame nothing ever read: loop counters never advanced and `externum vm` hung
  silently (the original benchmark hang). Store path now mirrors `_stmt_ASSIGN`
  (`STORE_GLOBAL` when not inside a function).
- **Issue #21 (related)** — the parser reports `"*="`-style operators with the
  `=` suffix, but the bytecode `op_map` was keyed on bare operators: every
  augmented op except `+=` silently degraded to addition. Also: `obj.attr += v`,
  `x[i] += v` and `*p += v` emitted no store at all — now desugared through the
  normal ASSIGN paths.
- **Issue #22** — parenthesized right-hand sides (`total + ((i*3+7) % 1000)`)
  reached the bytecode compiler as raw text and fell through to `_compile_name`
  (`undefined global (((...)))`). `_compile_simple_expr` now strips redundant
  outer parentheses before the literal/name dispatch.
- Lexer was missing `%=`, so `x %= 5` tokenized as `x % = 5` (parsed as a
  comparison against an unknown token); `%=` added to the lexer and to the
  parser's aug-assign dispatch.
- Issues #19 and #20 (empty bash/bytecode output for logic programs) are fully
  closed by the bash backend and the 4.1.0 artifact work respectively.

## [4.1.0] - 2026-09-19

### Added
- **Real bytecode artifacts**: `externum app.ext --target bytecode -o app.exbc`
  emits a self-contained `.exbc` file (magic header `EXBC` + version + payload).
  Run it with `externum run app.exbc` — the VM loads and executes it directly,
  skipping lexer/parser/compiler entirely. The source file never needs to ship.
- `module_to_bytes` / `module_from_bytes` / `save_module` / `load_module` in
  `externum.bytecode`, with magic/version/length validation.
- 2 new tests (artifact roundtrip executes identically; garbage rejection).

### Fixed
- (4.0.0) `--target bash` never worked; single-target `compile()` API now
  returns a dict — see 4.0.0 notes.

## [4.0.0] - 2026-09-19

### Fixed
- `externum file.ext --target bash` crashed with "list indices must be integers
  or slices, not str" — `Compiler.compile()` now returns a dict for single
  targets, matching what the CLI always expected. The bash target has never
  worked through the CLI before this release.
- Unknown `--target` values now raise a clear `ValueError` instead of
  returning an empty string.

### Changed
- Docs: test counts unified to the actual suite size (366), Why? section and a
  real end-to-end ASCII demo moved to the top of the README.

## [0.3.0] - 2026-09-15

### Added
- Native string interpolation: `$"Hello {name}, {a+b}!"` — lexer, parser, and both compilers (Python transpiler + bytecode VM)
- f-string-compatible escape semantics: `{{` and `}}` render as literal braces
- 8 new tests covering interpolation through both execution targets

## [0.2.0] - 2025-08-01

### Added
- Architecture documentation
- TUI IDE (terminal-based editor)
- Post-quantum crypto builtins
- Enhanced bytecode compiler
- 30+ instruction set
- Module system with imports
- Class/trait/impl system
- Pattern matching
- Generators and channels
- Macros
- Memory management (alloc/free)
- Full CI/CD pipeline

### Fixed
- Module import resolution
- Class instantiation
- Pattern matching with guards

## [0.1.0] - 2025-01-01

### Added
- Initial language design
- Lexer, parser, compiler
- VM execution engine
- Basic type system
