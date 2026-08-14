# Externum — Test Report & QA

> Generated: 2026-08-14 · Python 3 · Linux
> Re-run: `python3 -m unittest discover -s tests -v`

## Whole project

**✅ 167 tests · 0 failed · 0.3 s** — lexer, parser, compiler and runtime
conformance suites (`tests/test_externum.py`, `tests/test_extra.py`),
plus the NV2.0 hard-mode suite (`tests/test_hardmode.py`, 31 tests) and the
DRM suite (`tests/test_drm.py`, 16 tests).

## NV2.0 — Hard mode (`--hard`)

- **Macros** — expansion in expressions/statements, wrong-arg-count and
  zero-param macros, definitions stripped from the compiled output.
- **`match`/`case`** — literals (int/str/bool), binds + guards, list
  destructuring, wildcard, no-match raises at runtime.
- **Manual memory** — `alloc`/`free`/`@p` round-trip; compile-time rejection
  of **double-free**, **use-after-free**, deref of non-`Ptr`, `free()` of a
  non-pointer; runtime rejection of unknown pointer ids.
- **Type checker** — undeclared variables rejected, type mismatches
  rejected, `Int → Float` widening, bool expressions, function return-type
  conformance (good and bad).
- **Traits/impls** — satisfied impls run; missing methods and unknown traits
  rejected at compile time.
- **`unsafe`** — bypasses declaration/type checks.
- **Esoteric operators** — `≠`, `≈`, `←`.
- **Concurrency** — `spawn`/`chan`/`send`/`recv` round-trip.

## NV2.0 — DRM (`--protect`)

- **License keys** — make/verify, wrong secret rejected, tampered key
  rejected, expired rejected, garbage rejected.
- **Watermark** — app_id/author/build/source-SHA present in every artifact;
  artifact self-hash embedded.
- **Obfuscation** — plain payload strings absent from the output, `_ext_s()`
  helper present, and the obfuscated program still runs correctly.
- **Runtime guard** — runs with a valid license key; raises
  `invalid license key` with a wrong one; runs without a key.
- **`drm.ext` stdlib** — `sign`/`verify`/`watermark` executed from Externum.
- **CLI** — `keygen` (keys verify against the secret) and
  `compile --protect` (watermark in output); hard mode on a non-hard-mode
  file fails loudly.

## Notes

- Pure-Python implementation, zero third-party dependencies → fully
  deterministic test runs.
- No external services, network or GPU involved.
