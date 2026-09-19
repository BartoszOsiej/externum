# Changelog

All notable changes to Externum will be documented in this file.

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
