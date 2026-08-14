"""Externum — static analysis pipeline.

Externum is a strict language by design: every compilation runs the full
static analysis. There is no "easy mode" — these checks *are* the language.

`preprocess()` expands `macro` definitions before lexing (compile-time
metaprogramming).

`check()` runs the static type checker + ownership analyser over a parsed
AST using the metadata the parser captured (declared variable annotations,
function signatures, traits, impls, `mut` declarations). Any violation
raises `ExternumTypeError` with all diagnostics joined.
"""

import re
from typing import List, Optional, Set, Tuple

from .parser import ASTNode
from .typesys import TypeChecker, ExternumTypeError


_MACRO_DEF = re.compile(
    r'macro\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*\{([\s\S]*?)\}',
    re.MULTILINE,
)


class MacroError(Exception):
    """Raised when a macro is misused."""


def _split_args(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(',') if p.strip()]


def preprocess(source: str) -> Tuple[str, dict]:
    """Expand macro definitions. Returns (processed_source, macros)."""
    macros = {}
    for m in _MACRO_DEF.finditer(source):
        name, params, body = m.group(1), m.group(2), m.group(3)
        macros[name] = {'params': _split_args(params or ''), 'body': body}
    if not macros:
        return source, macros

    # strip definitions from the source
    cleaned = _MACRO_DEF.sub('', source)

    # expand NAME(...) and bare NAME invocations
    for name, macro in macros.items():
        cleaned = _expand(cleaned, name, macro)
    return cleaned, macros


def _expand(source: str, name: str, macro: dict) -> str:
    params = macro['params']
    body = macro['body']
    pattern = re.compile(r'\b' + re.escape(name) + r'\s*\(([^()]*)\)')
    pos = 0
    out = []
    for m in pattern.finditer(source):
        out.append(source[pos:m.start()])
        raw_args = m.group(1)
        args = _split_args(raw_args) if raw_args.strip() else []
        if len(args) != len(params):
            raise MacroError(
                f'macro `{name}` expects {len(params)} argument(s), got {len(args)}')
        expanded = body
        for pname, arg in zip(params, args):
            expanded = re.sub(r'\b' + re.escape(pname) + r'\b', arg, expanded)
        out.append(expanded)
        pos = m.end()
    out.append(source[pos:])
    return ''.join(out)


def check(ast: List[ASTNode], annotations: dict, signatures: dict,
          traits: dict, impls: dict, mutable: Set[str] = None) -> List[str]:
    """Run Externum static analysis. Returns the list of diagnostics."""
    checker = TypeChecker(ast, annotations, signatures, traits, impls, mutable or set())
    return checker.check()


def check_or_raise(ast: List[ASTNode], annotations: dict, signatures: dict,
                   traits: dict, impls: dict, mutable: Set[str] = None) -> None:
    errors = check(ast, annotations, signatures, traits, impls, mutable)
    if errors:
        raise ExternumTypeError(
            'Externum: ' + '; '.join(errors))
