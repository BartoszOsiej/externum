"""Externum Runtime — compiles and executes ``.ext`` programs.

Provides:
  - in-process execution of Externum source (transpile to Python, then exec)
  - an import hook so ``import module`` resolves ``module.ext`` files
  - an interactive REPL (``externum repl``)
"""

import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys

from .. import drm
from ..analysis import check_or_raise, preprocess
from ..compiler import Compiler
from ..lexer import Lexer
from ..parser import Parser
from .rtlib import externum_globals

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _ExtLoader(importlib.abc.Loader):
    """Compiles an ``.ext`` file to Python and loads it as a module."""

    def __init__(self, path: str, runtime: "Runtime"):
        self.path = path
        self._runtime = runtime

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        with open(self.path, encoding="utf-8") as fh:
            source = fh.read()
        code = self._runtime.compile_to_python(source)
        module.__dict__.update(externum_globals())
        exec(compile(code, self.path, "exec"), module.__dict__)


class _ExtFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder that resolves ``name.ext`` modules on the search path."""

    def __init__(self, runtime: "Runtime", roots):
        self._runtime = runtime
        self._roots = [os.path.abspath(r) for r in roots if r]

    def find_spec(self, fullname, path=None, target=None):
        rel = fullname.replace(".", os.sep)
        for root in self._roots:
            candidate = os.path.join(root, rel + ".ext")
            if os.path.isfile(candidate):
                return importlib.util.spec_from_loader(fullname, _ExtLoader(candidate, self._runtime))
        return None


class Runtime:
    """Executes Externum source, loads ``.ext`` modules and runs a REPL."""

    def __init__(self, search_roots=None):
        self.lexer_cls = Lexer
        self.parser_cls = Parser
        self.compiler_cls = Compiler
        roots = list(search_roots or [])
        roots += [os.getcwd(), os.path.join(_REPO_ROOT, "lib")]
        roots += [r for r in os.environ.get("EXTERNUM_PATH", "").split(":") if r]
        self._finder = _ExtFinder(self, roots)
        # insert after builtin/importlib finders but before path-based ones
        self._finder_index = None
        for i, f in enumerate(sys.meta_path):
            if f is importlib.machinery.PathFinder:
                self._finder_index = i
                break
        if self._finder_index is None:
            sys.meta_path.append(self._finder)
        else:
            sys.meta_path.insert(self._finder_index, self._finder)

    def __del__(self):
        try:
            if self._finder in sys.meta_path:
                sys.meta_path.remove(self._finder)
        except Exception:
            pass

    # ------------------------------------------------------------- core API
    def compile_to_python(self, source: str, protect: dict = None, check: bool = False) -> str:
        """Compile Externum source to Python.

        Type checking is off by default (check=False). Set check=True
        to run the strict type checker (declarations, annotations, ownership).

        - `protect={...}` — apply the full DRM stack to the output
          (keys: app_id, author, secret, build_id).
        """
        processed, _macros = preprocess(source)
        parser = self.parser_cls(self.lexer_cls(processed).tokenize())
        ast = list(parser.parse())
        if check:
            check_or_raise(ast, parser.annotations, parser.signatures, parser.traits, parser.impls, parser.mutable)
        result = self.compiler_cls(ast).compile("all")
        code = result["python"]
        if protect:
            code = drm.protect_python(
                code,
                app_id=protect.get("app_id", "externum-app"),
                author=protect.get("author", "unknown"),
                source=source,
                secret=protect.get("secret", "externum-drm"),
                build_id=protect.get("build_id"),
            )
        return code

    def run(
        self, source: str, filename: str = "<externum>", argv=None, protect: dict = None, check: bool = False
    ) -> dict:
        """Execute an Externum program string. Returns the module namespace."""
        old_argv = sys.argv
        sys.argv = [filename] + list(argv or [])
        try:
            return self._exec(source, filename, protect=protect, check=check)
        finally:
            sys.argv = old_argv

    def run_file(self, path: str, argv=None, protect: dict = None, check: bool = False) -> dict:
        path = os.path.abspath(path)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        # let the running script import sibling .ext modules
        self._finder._roots.insert(0, os.path.dirname(path))
        return self.run(source, filename=path, argv=argv, protect=protect, check=check)

    def _exec(self, source: str, filename: str, protect: dict = None, check: bool = False) -> dict:
        code = self.compile_to_python(source, protect=protect, check=check)
        ns = {"__name__": "__main__", "__file__": filename}
        ns.update(externum_globals())
        exec(compile(code, filename, "exec"), ns)
        return ns

    # ------------------------------------------------------------------ REPL
    def repl(self, banner: str = None) -> None:
        print(banner or f'Externum {_version()} — type "exit()" or Ctrl+D to quit.')
        ns = {"__name__": "__main__"}
        ns.update(externum_globals())
        buffer = []
        while True:
            prompt = "... " if buffer else ">>> "
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip() == "exit()" or line.strip() == "quit":
                break
            buffer.append(line)
            if not self._is_complete(buffer):
                continue
            code = "\n".join(buffer)
            buffer = []
            if not code.strip():
                continue
            try:
                python = self.compile_to_python(code)
                compiled = compile(python, "<repl>", "single" if python.count("\n") == 0 else "exec")
                exec(compiled, ns)
            except SystemExit:
                break
            except Exception as exc:
                print(f"Error: {exc}")

    def _is_complete(self, lines) -> bool:
        """True when the accumulated lines form a complete statement."""
        if not lines:
            return True
        if lines[-1].strip() == "":
            return True  # blank line closes an open block
        source = "\n".join(lines)
        if source.strip() == "":
            return True
        try:
            tokens = self.lexer_cls(source).tokenize()
        except SyntaxError:
            return False
        indent = 0
        for tok in tokens:
            if tok.type == "INDENT":
                indent += 1
            elif tok.type == "DEDENT":
                indent = max(0, indent - 1)
        if indent > 0:
            return False  # block not closed yet
        meaningful = [t for t in tokens if t.type not in ("NEWLINE", "INDENT", "DEDENT")]
        if meaningful and meaningful[-1].type in (
            "COLON",
            "ASSIGN",
            "PLUS",
            "MINUS",
            "TIMES",
            "DIVIDE",
            "COMMA",
            "POWER",
            "MOD",
            "&",
            "|",
            "^",
            "<<",
            ">>",
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
            "+=",
            "-=",
            "=",
            "**",
        ):
            return False  # expression continues
        return True


def _version() -> str:
    try:
        from .. import __version__

        return __version__
    except Exception:  # pragma: no cover
        return "3.0.0"
