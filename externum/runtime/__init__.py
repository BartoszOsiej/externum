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

from ..lexer import Lexer
from ..parser import Parser
from ..compiler import Compiler

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _ExtLoader(importlib.abc.Loader):
    """Compiles an ``.ext`` file to Python and loads it as a module."""

    def __init__(self, path: str, runtime: 'Runtime'):
        self.path = path
        self._runtime = runtime

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        with open(self.path, 'r', encoding='utf-8') as fh:
            source = fh.read()
        code = self._runtime.compile_to_python(source)
        exec(compile(code, self.path, 'exec'), module.__dict__)


class _ExtFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder that resolves ``name.ext`` modules on the search path."""

    def __init__(self, runtime: 'Runtime', roots):
        self._runtime = runtime
        self._roots = [os.path.abspath(r) for r in roots if r]

    def find_spec(self, fullname, path=None, target=None):
        rel = fullname.replace('.', os.sep)
        for root in self._roots:
            candidate = os.path.join(root, rel + '.ext')
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
        roots += [os.getcwd(), os.path.join(_REPO_ROOT, 'lib')]
        roots += [r for r in os.environ.get('EXTERNUM_PATH', '').split(':') if r]
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
    def compile_to_python(self, source: str) -> str:
        tokens = self.lexer_cls(source).tokenize()
        ast = list(self.parser_cls(tokens).parse())
        result = self.compiler_cls(ast).compile('all')
        return result['python']

    def run(self, source: str, filename: str = '<externum>', argv=None) -> dict:
        """Execute an Externum program string. Returns the module namespace."""
        old_argv = sys.argv
        sys.argv = [filename] + list(argv or [])
        try:
            return self._exec(source, filename)
        finally:
            sys.argv = old_argv

    def run_file(self, path: str, argv=None) -> dict:
        path = os.path.abspath(path)
        with open(path, 'r', encoding='utf-8') as fh:
            source = fh.read()
        # let the running script import sibling .ext modules
        self._finder._roots.insert(0, os.path.dirname(path))
        return self.run(source, filename=path, argv=argv)

    def _exec(self, source: str, filename: str) -> dict:
        code = self.compile_to_python(source)
        ns = {'__name__': '__main__', '__file__': filename}
        exec(compile(code, filename, 'exec'), ns)
        return ns

    # ------------------------------------------------------------------ REPL
    def repl(self, banner: str = None) -> None:
        print(banner or f'Externum {_version()} — type "exit()" or Ctrl+D to quit.')
        ns = {'__name__': '__main__'}
        buffer = []
        while True:
            prompt = '... ' if buffer else '>>> '
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip() == 'exit()' or line.strip() == 'quit':
                break
            buffer.append(line)
            if not self._is_complete(buffer):
                continue
            code = '\n'.join(buffer)
            buffer = []
            if not code.strip():
                continue
            try:
                python = self.compile_to_python(code)
                compiled = compile(python, '<repl>', 'single' if python.count('\n') == 0 else 'exec')
                exec(compiled, ns)
            except SystemExit:
                break
            except Exception as exc:  # noqa: BLE001 - REPL boundary
                print(f'Error: {exc}')

    def _is_complete(self, lines) -> bool:
        """True when the accumulated lines form a complete statement."""
        if not lines:
            return True
        if lines[-1].strip() == '':
            return True  # blank line closes an open block
        source = '\n'.join(lines)
        if source.strip() == '':
            return True
        try:
            tokens = self.lexer_cls(source).tokenize()
        except SyntaxError:
            return False
        indent = 0
        for tok in tokens:
            if tok.type == 'INDENT':
                indent += 1
            elif tok.type == 'DEDENT':
                indent = max(0, indent - 1)
        if indent > 0:
            return False  # block not closed yet
        meaningful = [t for t in tokens if t.type not in ('NEWLINE', 'INDENT', 'DEDENT')]
        if meaningful and meaningful[-1].type in ('COLON', 'ASSIGN', 'PLUS', 'MINUS',
                                                  'TIMES', 'DIVIDE', 'COMMA',
                                                  'POWER', 'MOD', '&', '|', '^',
                                                  '<<', '>>', '==', '!=', '<', '>',
                                                  '<=', '>=', '+=', '-=', '=', '**'):
            return False  # expression continues
        return True


def _version() -> str:
    try:
        from .. import __version__
        return __version__
    except Exception:  # pragma: no cover
        return '3.0.0'
