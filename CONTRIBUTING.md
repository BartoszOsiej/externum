# Contributing to Externum

Thanks for your interest in contributing! Externum is a language built from
scratch, and every contribution matters.

## Quick Start

```bash
git clone https://github.com/BartoszOsiej/externum.git
cd externum
pip install -e .
python3 -m unittest discover -s tests -v   # 192 tests must pass
```

## Ways to Contribute

### 🐛 Bug Reports
Open an issue with:
- Externum code that reproduces the bug
- Expected vs actual output
- Python version and OS

### ✨ New Features
1. Fork the repo
2. Create a branch: `git checkout -b feat/my-feature`
3. Add tests in `tests/`
4. Run the full suite: `python3 -m unittest discover -s tests -v`
5. Open a PR

### 📚 Standard Library
Add new functions to `lib/` modules:
- `structs` — data structures
- `strings` — string manipulation
- `mathx` — math utilities
- `fs` — filesystem operations
- `jsonx` — JSON handling
- `net` — networking

Each function needs:
- Implementation in the `.ext` module
- Unit tests in `tests/`
- Documentation in WIKI.md

### 🌐 Browser Playground
The playground runs on GitHub Pages via Pyodide. To contribute:
1. Edit files in `docs/projects/externum/`
2. Test locally with `npm run start` in the docs site
3. Open a PR — it auto-deploys on merge

### 🤖 Issue-Command Bot
- `/run <code>` — executes Externum code in CI
- `/define <name> <body>` — adds a new stdlib function via PR

## Code Style

- **Pythonic** — follow PEP 8 for Python code
- **Externum** — follow the language spec in WIKI.md
- **Tests** — every feature needs test coverage
- **DRM** — never break the license verification chain

## Development Setup

```bash
# Install dev dependencies
pip install -e .

# Run specific test file
python3 -m pytest tests/test_lexer.py -v

# Run with coverage
python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report
```

## Code of Conduct

Be respectful, constructive, and welcoming. We're building something cool
together.

## License

By contributing, you agree that your contributions will be licensed under MIT.
