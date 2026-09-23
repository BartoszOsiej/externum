"""externum.translate — source-to-source translators into Externum.

Two pragmatic translators that turn existing Python and Rust code into
Externum (`.ext`) sources:

- :func:`translate_python` — AST-based (uses the stdlib ``ast`` module),
  so the Python input is parsed by Python itself. Types are inferred for
  the strict Externum declaration syntax (``x: Int = ...``), f-strings
  become ``$"..."``, and ``if __name__ == "__main__":`` bodies are
  hoisted into ``fn main():`` (Externum auto-runs ``main()``).

- :func:`translate_rust` — line-based with a brace-to-indent engine.
  Handles the pragmatic core of the language: ``fn``/``let``/``struct``/
  ``enum``/``impl`` (→ class methods), ``match`` arms (→ ``case``),
  ``println!``/``format!`` (→ ``print``/``$"..."``), ``vec!`` and common
  method shorthands (``len()``, ``push()``, ``to_string()`` ...).

Both translators are best-effort by design: everything they cannot map
is reported as a warning (collect with ``--report``) instead of being
silently mangled. Run the result through ``externum check`` and the
usual compile/run pipeline afterwards.
"""

from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Shared reporting
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TranslationReport:
    """Warnings + short stats gathered during a translation."""

    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def warn(self, msg: str, lineno: int | None = None) -> None:
        prefix = f"line {lineno}: " if lineno else ""
        self.warnings.append(f"{prefix}{msg}")

    def bump(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n

    def summary(self) -> str:
        lines = [f"  {k}: {v}" for k, v in sorted(self.stats.items())]
        if self.warnings:
            lines.append("  warnings:")
            lines += [f"    - {w}" for w in self.warnings]
        return "\n".join(lines) if lines else "  (clean)"


# ─────────────────────────────────────────────────────────────────────────────
# Python → Externum
# ─────────────────────────────────────────────────────────────────────────────

_KNOWN_EXTERNUM_STDLIB = {"mathx", "strings", "structs", "fs", "jsonx", "geometry", "net", "drm", "compiler"}

_PY2EXT_TYPES = {
    "int": "Int",
    "float": "Float",
    "str": "Str",
    "bool": "Bool",
    "list": "List",
    "dict": "Dict",
    "set": "Set",
    "tuple": "Tuple",
    "object": "Any",
    "bytes": "Str",
}


class _Py2Ext(ast.NodeVisitor):
    """Emit Externum source from a parsed Python module."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.indent = 0
        self.report = TranslationReport()
        # declared names per scope (module scope + one entry per function)
        self._module_names: set[str] = set()
        self._scope: set[str] = self._module_names
        self._fstr_slots: list[str] = []  # placeholders replaced after unparse

    # ── helpers ──
    def _emit(self, line: str) -> None:
        self.out.append("    " * self.indent + line if line else "")

    def _declare(self, name: str) -> None:
        self._scope.add(name)

    def _is_declared(self, name: str) -> bool:
        return name in self._scope

    # ── expressions ──
    def _render_fstr(self, node: ast.JoinedStr) -> str:
        """Render an f-string as an Externum ``$"..."`` literal."""
        parts: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                text = str(v.value).replace("\\", "\\\\").replace('"', '\\"')
                text = text.replace("{", "{{").replace("}", "}}")
                parts.append(text)
            elif isinstance(v, ast.FormattedValue):
                inner = self._expr(v.value)
                spec = ""
                if v.format_spec is not None:
                    spec = ":" + self._expr(v.format_spec).strip("'\"")
                conv = "!r" if v.conversion == 114 else "!s" if v.conversion == 115 else ""
                parts.append("{" + inner + conv + spec + "}")
        return '$"' + "".join(parts) + '"'

    def _fstr_placeholder(self, node: ast.JoinedStr) -> str:
        """Register a rendered f-string and return its placeholder token."""
        self._fstr_slots.append(self._render_fstr(node))
        return f"__EXT_FSTR_{len(self._fstr_slots) - 1}__"

    def _swap_fstr(self, node: ast.expr) -> ast.expr:
        """Deep-copy ``node`` replacing every f-string with a placeholder Name,

        so ``ast.unparse`` never renders ``f'...'`` back into the output.
        """
        if not any(isinstance(n, ast.JoinedStr) for n in ast.walk(node)):
            return node

        class _Swap(ast.NodeTransformer):
            def visit_JoinedStr(self, n: ast.JoinedStr) -> ast.expr:  # noqa: N802
                return ast.copy_location(
                    ast.Name(id=self.conv._fstr_placeholder(n), ctx=ast.Load()), n
                )

        swapper = _Swap()
        swapper.conv = self
        fixed = swapper.visit(copy.deepcopy(node))
        ast.fix_missing_locations(fixed)
        return fixed

    def _expr(self, node: ast.expr) -> str:
        return ast.unparse(self._swap_fstr(node))

    # ── types ──
    def _map_type(self, ann: ast.expr) -> str:
        if isinstance(ann, ast.Constant) and ann.value is None:
            return "Void"
        if isinstance(ann, ast.Name):
            return _PY2EXT_TYPES.get(ann.id, ann.id)
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            return _PY2EXT_TYPES.get(ann.value, ann.value)
        if isinstance(ann, ast.Subscript):
            base = self._map_type(ann.value)
            inner = ann.slice
            if isinstance(inner, ast.Tuple):
                elems = [self._map_type(e) for e in inner.elts]
                inner_txt = ", ".join(elems)
            else:
                inner_txt = self._map_type(inner)
            return f"{base}[{inner_txt}]"
        return ast.unparse(ann)

    def _infer(self, value: ast.expr) -> str | None:
        if isinstance(value, ast.Constant):
            if value.value is None:
                return "Void"
            if isinstance(value.value, bool):
                return "Bool"
            if isinstance(value.value, int):
                return "Int"
            if isinstance(value.value, float):
                return "Float"
            if isinstance(value.value, str):
                return "Str"
            return None
        if isinstance(value, ast.JoinedStr):
            return "Str"
        if isinstance(value, ast.List):
            elem_types = [self._infer(e) for e in value.elts]
            concrete = {t for t in elem_types if t}
            if not value.elts:
                return "List[Any]"
            if len(concrete) == 1:
                return f"List[{concrete.pop()}]"
            return "List[Any]"
        if isinstance(value, ast.Set):
            return "Set[Any]"
        if isinstance(value, ast.Dict):
            key_types = {self._infer(k) for k in value.keys if k is not None}
            val_types = {self._infer(v) for v in value.values}
            kt = key_types.pop() if len(key_types) == 1 else "Any"
            vt = val_types.pop() if len(val_types) == 1 else "Any"
            return f"Dict[{kt}, {vt}]"
        if isinstance(value, ast.Tuple):
            return "Tuple"
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in _PY2EXT_TYPES:
            return _PY2EXT_TYPES[value.func.id].capitalize() if value.func.id == "str" else _PY2EXT_TYPES[value.func.id].capitalize()
        if isinstance(value, ast.BinOp):
            lt, rt = self._infer(value.left), self._infer(value.right)
            if isinstance(value.op, ast.Add) and (lt == "Str" or rt == "Str"):
                return "Str"
            if lt in ("Int", "Float") or rt in ("Int", "Float"):
                return "Float" if "Float" in (lt, rt) else "Int"
        return None

    # ── statements ──
    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self._stmt(stmt)

    def _docstring_comment(self, node: ast.AST) -> None:
        doc = ast.get_docstring(node)
        if doc:
            for line in doc.splitlines():
                self._emit(f"# {line}".rstrip())

    def _stmt(self, stmt: ast.stmt) -> None:
        # NOTE: attribute-target assignments (self.x = ...) are handled inside
        # _assign; this dispatch covers every other statement kind.
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            self._function(stmt)
        elif isinstance(stmt, ast.ClassDef):
            self._class(stmt)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            tgt = stmt.target.id
            ann = self._map_type(stmt.annotation)
            val = self._expr(stmt.value) if stmt.value else "None"
            self._emit(f"{tgt}: {ann} = {val}")
            self._declare(tgt)
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Attribute):
            # e.g. self.name = name — attribute targets pass through verbatim
            self._emit(f"{ast.unparse(stmt.targets[0])} = {self._expr(stmt.value)}")
        elif isinstance(stmt, ast.Assign):
            self._assign(stmt)
        elif isinstance(stmt, ast.AugAssign):
            self._aug_assign(stmt)
        elif isinstance(stmt, ast.Return):
            self._emit(f"return {self._expr(stmt.value)}" if stmt.value else "return")
        elif isinstance(stmt, ast.If):
            self._if(stmt)
        elif isinstance(stmt, ast.While):
            self._emit(f"while {self._expr(stmt.test)}:")
            self._body(stmt)
        elif isinstance(stmt, ast.For):
            self._for(stmt)
        elif isinstance(stmt, ast.Break):
            self._emit("break")
        elif isinstance(stmt, ast.Continue):
            self._emit("continue")
        elif isinstance(stmt, ast.Pass):
            self._emit("pass")
        elif isinstance(stmt, ast.Try):
            self._try(stmt)
        elif isinstance(stmt, ast.With):
            self._with(stmt)
        elif isinstance(stmt, ast.Raise):
            self._raise(stmt)
        elif isinstance(stmt, ast.Import):
            self._import(stmt)
        elif isinstance(stmt, ast.ImportFrom):
            self._import_from(stmt)
        elif isinstance(stmt, ast.Global | ast.Nonlocal):
            self._emit(f"{type(stmt).__name__.lower()} {', '.join(stmt.names)}")
        elif isinstance(stmt, ast.Delete):
            self._emit(f"del {', '.join(self._expr(t) for t in stmt.targets)}")
        elif isinstance(stmt, ast.Assert):
            self._emit(f"assert {self._expr(stmt.test)}")
        elif isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                # module/class-level bare string → emit as comment
                for line in str(stmt.value.value).splitlines():
                    self._emit(f"# {line}".rstrip())
            else:
                self._emit(self._expr(stmt.value))
        else:
            self.report.warn(f"unsupported statement: {type(stmt).__name__} — skipped", getattr(stmt, "lineno", None))

    def _assign(self, stmt: ast.Assign) -> None:
        if isinstance(stmt.targets[0], ast.Attribute):
            # e.g. self.name = name — attribute targets pass through verbatim
            self._emit(f"{ast.unparse(stmt.targets[0])} = {self._expr(stmt.value)}")
            return
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            tgt_txt = ", ".join(ast.unparse(t) for t in stmt.targets)
            self.report.warn(f"tuple/attribute assignment needs manual types: {tgt_txt} = ...", stmt.lineno)
            self._emit(f"# TODO declare types: {tgt_txt} = {self._expr(stmt.value)}")
            return
        name = stmt.targets[0].id
        value = stmt.value
        if self._is_declared(name):
            self._emit(f"{name} = {self._expr(value)}")
        else:
            inferred = self._infer(value)
            if inferred:
                self._emit(f"{name}: {inferred} = {self._expr(value)}")
            else:
                self.report.warn(f"could not infer type of '{name}' — declared as Any", stmt.lineno)
                self._emit(f"{name}: Any = {self._expr(value)}")
            self._declare(name)

    def _aug_assign(self, stmt: ast.AugAssign) -> None:
        if not isinstance(stmt.target, ast.Name) or not self._is_declared(stmt.target.id):
            self.report.warn("augmented assignment to undeclared name — rewritten", stmt.lineno)
        op_txt = type(stmt.op).__name__
        op_map = {"Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "//", "Mod": "%", "Pow": "**"}
        op = op_map.get(op_txt, "+")
        self._emit(f"{ast.unparse(stmt.target)} = {ast.unparse(stmt.target)} {op} {self._expr(stmt.value)}")

    def _function(self, stmt: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if isinstance(stmt, ast.AsyncFunctionDef):
            self.report.warn("async function translated as sync (Externum has no async yet)", stmt.lineno)
        args = stmt.args
        if args.vararg or args.kwarg or args.kwonlyargs:
            self.report.warn(f"*args/**kwargs on '{stmt.name}' dropped — Externum functions are fixed-arity", stmt.lineno)
        params = []
        defaults = [""] * (len(args.args) - len(args.defaults)) + [ast.unparse(d) for d in args.defaults]
        for arg, default in zip(args.args, defaults):
            if arg.arg == "self":
                params.append("self")
                continue
            ann = f": {self._map_type(arg.annotation)}" if arg.annotation else ""
            dflt = f" = {default}" if default else ""
            params.append(f"{arg.arg}{ann}{dflt}")
        ret = ""
        if stmt.returns is not None:
            mapped = self._map_type(stmt.returns)
            if mapped != "Void":
                ret = f" -> {mapped}"
        self._emit(f"def {stmt.name}({', '.join(params)}){ret}:")
        self._docstring_comment(stmt)
        outer, self._scope = self._scope, set()
        self.indent += 1
        if not stmt.body or (len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Pass) and not ast.get_docstring(stmt)):
            self._emit("pass")
        else:
            for s in stmt.body:
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
                    continue  # docstring already emitted
                self._stmt(s)
        self.indent -= 1
        self._scope = outer
        self._declare(stmt.name)

    def _class(self, stmt: ast.ClassDef) -> None:
        bases = ", ".join(ast.unparse(b) for b in stmt.bases)
        self._emit(f"class {stmt.name}({bases}):" if bases else f"class {stmt.name}:")
        self._docstring_comment(stmt)
        self.indent += 1
        body = [s for s in stmt.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        has_init = any(isinstance(s, ast.FunctionDef) and s.name == "__init__" for s in body)
        if not body:
            self._emit("pass")
        else:
            if not has_init and not any(isinstance(s, ast.FunctionDef) for s in body):
                self._emit("def __init__(self):")
                self.indent += 1
                self._emit("pass")
                self.indent -= 1
            for s in body:
                self._stmt(s)
        self.indent -= 1
        self._declare(stmt.name)

    def _if(self, stmt: ast.If) -> None:
        self._emit(f"if {self._expr(stmt.test)}:")
        self._body(stmt)
        for elif_ in stmt.orelse:
            if isinstance(elif_, ast.If) and len(stmt.orelse) == 1:
                self._emit(f"elif {self._expr(elif_.test)}:")
                self._body(elif_)
                if elif_.orelse:
                    self._emit("else:")
                    self.indent += 1
                    for s in elif_.orelse:
                        self._stmt(s)
                    self.indent -= 1
                return
            self._emit("else:")
            self.indent += 1
            self._stmt(elif_)
            self.indent -= 1

    def _for(self, stmt: ast.For) -> None:
        tgt = stmt.target
        if isinstance(tgt, ast.Name):
            target = tgt.id
            if not self._is_declared(target):
                self._emit(f"{target}: Any = None")
                self._declare(target)
        elif isinstance(tgt, ast.Tuple):
            names = [e.id for e in tgt.elts if isinstance(e, ast.Name)]
            for n in names:
                if not self._is_declared(n):
                    self._emit(f"{n}: Any = None")
                    self._declare(n)
            target = ast.unparse(tgt)
        else:
            target = ast.unparse(tgt)
        self._emit(f"for {target} in {self._expr(stmt.iter)}:")
        self._body(stmt)

    def _try(self, stmt: ast.Try) -> None:
        self._emit("try:")
        self._body(stmt)
        for handler in stmt.handlers:
            exc = self._map_type(handler.type) if handler.type else ""
            name = f" as {handler.name}" if handler.name else ""
            self._emit(f"except {exc}{name}:" if exc else "except" + (name or ":"))
            self.indent += 1
            for s in handler.body:
                self._stmt(s)
            self.indent -= 1
        if stmt.orelse:
            self._emit("else:")
            self.indent += 1
            for s in stmt.orelse:
                self._stmt(s)
            self.indent -= 1
        if stmt.finalbody:
            self._emit("finally:")
            self.indent += 1
            for s in stmt.finalbody:
                self._stmt(s)
            self.indent -= 1

    def _with(self, stmt: ast.With) -> None:
        items = ", ".join(
            f"{self._expr(i.context_expr)} as {ast.unparse(i.optional_vars)}" if i.optional_vars else self._expr(i.context_expr)
            for i in stmt.items
        )
        self._emit(f"with {items}:")
        self._body(stmt)

    def _raise(self, stmt: ast.Raise) -> None:
        if stmt.exc is None:
            self._emit("raise")
        else:
            cause = f" from {self._expr(stmt.cause)}" if stmt.cause else ""
            self._emit(f"raise {self._expr(stmt.exc)}{cause}")

    def _import(self, stmt: ast.Import) -> None:
        for alias in stmt.names:
            top = alias.name.split(".")[0]
            if top not in _KNOWN_EXTERNUM_STDLIB:
                self.report.warn(f"import {alias.name}: not part of the Externum stdlib — runtime import may fail", stmt.lineno)
            if alias.asname:
                self._emit(f"import {alias.name} as {alias.asname}")
            else:
                self._emit(f"import {alias.name}")
            self._declare(alias.asname or top)

    def _import_from(self, stmt: ast.ImportFrom) -> None:
        mod = stmt.module or ""
        if stmt.level:
            self.report.warn("relative import — not supported, skipped", stmt.lineno)
            return
        if mod.split(".")[0] not in _KNOWN_EXTERNUM_STDLIB:
            self.report.warn(f"from {mod} import ...: not part of the Externum stdlib — runtime import may fail", stmt.lineno)
        names = ", ".join(f"{a.name} as {a.asname}" if a.asname else a.name for a in stmt.names)
        self._emit(f"from {mod} import {names}")
        for a in stmt.names:
            self._declare(a.asname or a.name)

    def _body(self, stmt: ast.stmt) -> None:
        self.indent += 1
        body = stmt.body
        if not body:
            self._emit("pass")
        else:
            for s in body:
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
                    continue
                self._stmt(s)
        self.indent -= 1

    def finish(self) -> str:
        text = "\n".join(self.out) + "\n"
        for i, literal in enumerate(self._fstr_slots):
            text = text.replace(f"__EXT_FSTR_{i}__", literal)
        return text


def _py_str_requote(text: str) -> str:
    """Normalise ast.unparse's single-quoted strings to double quotes.

    Externum accepts both, but $"..." interpolation and the docs use double
    quotes — keeps translated output idiomatic.
    """

    def _requote(m: re.Match) -> str:
        inner = m.group(1)
        if '"' in inner:
            return m.group(0)  # contains double quotes — keep single-quoted
        if "\\" in inner:
            return m.group(0)
        return f'"{inner}"'

    # only outside $"..." f-string slots (those are substituted later, so
    # placeholders are what we see here)
    return re.sub(r"'([^'\n]*)'", _requote, text)


def _hoist_main(tree: ast.Module) -> bool:
    """Replace the ``if __name__ == "__main__":`` guard with ``def main():``.

    Externum runs ``main()`` automatically, so this keeps the translated
    program's behaviour identical to the original script.
    """
    for i, stmt in enumerate(tree.body):
        if isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare):
            t = stmt.test
            if (
                isinstance(t.left, ast.Name)
                and t.left.id == "__name__"
                and isinstance(t.comparators[0], ast.Constant)
                and t.comparators[0].value == "__main__"
                and len(t.ops) == 1
            ):
                tree.body[i] = ast.FunctionDef(
                    name="main",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=stmt.body,
                    decorator_list=[],
                    returns=None,
                    type_comment=None,
                    lineno=stmt.lineno,
                )
                ast.fix_missing_locations(tree)
                return True
    return False


def translate_python(source: str, filename: str = "<source>") -> tuple[str, TranslationReport]:
    """Translate Python ``source`` into Externum source."""
    tree = ast.parse(source, filename=filename)
    hoisted = _hoist_main(tree)
    conv = _Py2Ext()
    conv.visit_Module(tree)
    header = ["# Translated from Python by `externum translate` (py2ext)"]
    if hoisted:
        header.append("# `if __name__ == \"__main__\"` hoisted into main() — Externum auto-runs it")
    return _py_str_requote(conv.finish()), conv.report


# ─────────────────────────────────────────────────────────────────────────────
# Rust → Externum
# ─────────────────────────────────────────────────────────────────────────────

_RS_TYPE_MAP = {
    "i8": "Int", "i16": "Int", "i32": "Int", "i64": "Int", "i128": "Int", "isize": "Int",
    "u8": "Int", "u16": "Int", "u32": "Int", "u64": "Int", "u128": "Int", "usize": "Int",
    "f32": "Float", "f64": "Float",
    "bool": "Bool", "char": "Str", "str": "Str", "String": "Str",
}

_RS_METHOD_MAP = [
    (re.compile(r"([\w\.\[\]]+)\.len\(\)"), r"len(\1)"),
    (re.compile(r"([\w\.\[\]]+)\.abs\(\)"), r"abs(\1)"),
    (re.compile(r"([\w\.\[\]]+)\.to_string\(\)"), r"str(\1)"),
    (re.compile(r"String::from\(([^()]*)\)"), r"str(\1)"),
    (re.compile(r"\.clone\(\)"), r""),
    (re.compile(r"\.push\(([^()]*)\)"), r".append(\1)"),
    (re.compile(r"\bvec!\[([^\[\]]*)\]"), r"[\1]"),
]

_RS_OPS = [
    (re.compile(r"&&"), " and "),
    (re.compile(r"\|\|"), " or "),
    # negation — lookbehind also excludes word chars so `println!`/`vec!`
    # macro invocations keep their bang.
    (re.compile(r"(?<![\w!<>=])!(?=[\w\(:])"), "not "),
]


def _map_rs_type(t: str) -> str:
    t = t.strip()
    t = re.sub(r"&+\s*", "", t)
    t = re.sub(r"\bmut\s+", "", t)
    m = re.fullmatch(r"(Option|Result|Vec|Box|Rc|Arc)<(.+)>", t)
    if m:
        outer, inner = m.group(1), m.group(2)
        base = {"Vec": "List", "Box": "", "Rc": "", "Arc": ""}.get(outer, outer)
        inner_t = _map_rs_type(inner)
        return f"{base}[{inner_t}]" if base else inner_t
    if t in _RS_TYPE_MAP:
        return _RS_TYPE_MAP[t]
    return t


def _fmt_macro_to_extfmt(fmt: str, arg_exprs: list[str]) -> str:
    """`"x {} y {}"` + [a, b]  →  `x {a} y {b}` (Externum $\"...\" interpolation)."""
    out, args, i = [], list(arg_exprs), 0
    while i < len(fmt):
        if fmt.startswith("{{", i):
            out.append("{{")
            i += 2
        elif fmt.startswith("}}", i):
            out.append("}}")
            i += 2
        elif fmt.startswith("{}", i):
            out.append("{" + (args.pop(0) if args else "?") + "}")
            i += 2
        else:
            out.append(fmt[i])
            i += 1
    return "".join(out)


def _split_args(s: str) -> list[str]:
    """Split macro/argument list on top-level commas (strings + nesting aware)."""
    parts, depth, cur, i, in_str = [], 0, "", 0, False
    while i < len(s):
        c = s[i]
        if in_str:
            cur += c
            if c == '"' and s[i - 1] != "\\":
                in_str = False
        elif c == '"':
            in_str = True
            cur += c
        elif c in "([{":
            depth += 1
            cur += c
        elif c in ")]}":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip():
        parts.append(cur.strip())
    return parts


class _Rs2Ext:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.indent = 0
        self.report = TranslationReport()

    @staticmethod
    def _is_tail(idx: int, lines: list[str]) -> bool:
        """True when lines[idx] is the last statement before a closing brace."""
        for later in lines[idx + 1 :]:
            s = later.strip()
            if not s:
                continue
            return s.startswith("}")
        return False

    # ── line conversions ──
    def _types(self, line: str) -> str:
        line = re.sub(r"\b(\d+)[iu]\d+\b", r"\1", line)
        line = re.sub(r"\b(\d+(?:\.\d+)?)f32\b", r"\1", line)
        line = re.sub(r"\b(\d+(?:\.\d+)?)f64\b", r"\1", line)
        line = re.sub(r"\btrue\b", "True", line)
        line = re.sub(r"\bfalse\b", "False", line)
        for rx, repl in _RS_METHOD_MAP:
            line = rx.sub(repl, line)
        for rx, repl in _RS_OPS:
            line = rx.sub(repl, line)
        return line

    def _signature(self, line: str) -> str:
        """Convert `fn name<T>(args) -> Ret` → `fn name(args) -> Ret:` (no brace)."""
        line = re.sub(r"\bfn\s+", "fn ", line)
        line = re.sub(r"<[^<>]*>\s*(?=\()", "", line)  # generic params on fn
        m = re.match(r"fn\s+(\w+)\s*\((.*)\)\s*(?:->\s*(.+?))?\s*$", line, re.S)
        if not m:
            return line
        name, raw_args, ret = m.group(1), m.group(2), m.group(3)
        params = []
        for a in _split_args(raw_args):
            if a in ("&self", "&mut self", "self"):
                params.append("self")
                continue
            a = re.sub(r"\bmut\s+", "", a)
            if ":" in a:
                pname, ptype = a.split(":", 1)
                params.append(f"{pname.strip()}: {_map_rs_type(ptype)}")
            else:
                params.append(f"{a}: Any")
        ret_txt = ""
        if ret and ret.strip() not in ("()",):
            mapped = _map_rs_type(ret.strip())
            if mapped not in ("Void", ""):
                ret_txt = f" -> {mapped}"
        return f"fn {name}({', '.join(params)}){ret_txt}"

    def _macro(self, line: str) -> str:
        """println!/print!/format!/eprintln! → print / $"..."."""
        m = re.match(r'(eprintln!|eprint!|println!|print!|format!)\s*\((.*)\)\s*;?\s*$', line)
        if not m:
            return line
        macro, raw = m.group(1), m.group(2)
        args = _split_args(raw)
        if not args:
            return "print()" if macro != "format!" else '""'
        first = args[0]
        if not (first.startswith('"') and first.endswith('"')):
            self.report.warn(f"non-literal first argument to {macro} left as-is")
            return line
        fmt = first[1:-1]
        if macro == "format!":
            return f'$"{_fmt_macro_to_extfmt(fmt, args[1:])}"'
        if macro.startswith("e"):
            self.report.warn(f"{macro}! mapped to print (no stderr in Externum)")
        text = _fmt_macro_to_extfmt(fmt, args[1:])
        if args[1:] or fmt.endswith("\\n") or "\n" not in fmt:
            pass
        if macro in ("println!", "eprintln!"):
            return f'print($"' + text + '")' if args[1:] else f'print("{text}")'
        return f'print($"' + text + '")' if args[1:] else f'print("{text}")'

    def _let(self, line: str) -> str:
        m = re.match(r"let\s+(mut\s+)?(_\s+)?([\w]+)\s*(?::\s*([^=]+?))?\s*=\s*(.+?)\s*;?\s*$", line)
        if not m:
            return line
        name, ann, value = m.group(3), m.group(4), m.group(5)
        if ann:
            return f"{name}: {_map_rs_type(ann)} = {self._types(value)}"
        inferred: str | None = None
        v = value.strip()
        if re.fullmatch(r"-?\d+", v):
            inferred = "Int"
        elif re.fullmatch(r"-?\d+\.\d+", v):
            inferred = "Float"
        elif v.startswith('"'):
            inferred = "Str"
        elif v in ("true", "True", "false", "False"):
            inferred = "Bool"
        elif v.startswith("vec![") or (v.startswith("[") and v.endswith("]")):
            inferred = "List[Any]"
        if inferred:
            return f"{name}: {inferred} = {self._types(value)}"
        self.report.warn(f"could not infer type of '{name}' — declared as Any")
        return f"{name}: Any = {self._types(value)}"

    def _struct_literal(self, line: str) -> str:
        # single-line `Name { field: value, ... }` → `Name(field=value, ...)`
        return re.sub(
            r"\b([A-Z]\w*)\s*\{\s*([^{}]+?)\s*\}",
            lambda m: f"{m.group(1)}({', '.join(f.strip().replace(': ', '=', 1) for f in m.group(2).split(','))})"
            if ":" in m.group(2)
            else m.group(0),
            line,
        )

    # ── main loop ──
    def run(self, source: str) -> str:
        lines = source.splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            i += 1
            if not line:
                self.out.append("")
                continue
            # attributes & inner doc comments
            if line.startswith("#["):
                continue
            if line.startswith("///") or line.startswith("//!"):
                self._emit("# " + line.lstrip("/ "))
                continue
            # use statements → comments (crate paths don't exist in Externum)
            if line.startswith("use "):
                self._emit(f"# {line}")
                continue
            # struct definitions (collect the block)
            m = re.match(r"(?:pub\s+)?struct\s+(\w+)\s*\{(.*)\}\s*$", line)
            if m:
                fields = [f.strip() for f in m.group(2).split(",") if f.strip()]
                mapped = []
                for f in fields:
                    fname, _, ftype = f.partition(":")
                    mapped.append(f"{fname.strip()}: {_map_rs_type(ftype)}")
                self._emit(f"struct {m.group(1)} {{ {', '.join(mapped)} }}")
                continue
            m = re.match(r"(?:pub\s+)?struct\s+(\w+)\s*\{", line)
            if m:
                fields = []
                while i < len(lines) and "}" not in lines[i]:
                    f = lines[i].strip().rstrip(",").strip()
                    i += 1
                    if not f:
                        continue
                    fname, _, ftype = f.partition(":")
                    fields.append(f"{fname.strip()}: {_map_rs_type(ftype)}")
                i += 1  # closing brace
                self._emit(f"struct {m.group(1)} {{ {', '.join(fields)} }}")
                continue
            m = re.match(r"(?:pub\s+)?enum\s+(\w+)\s*\{(.*)\}\s*$", line)
            if m:
                variants = [v.strip() for v in m.group(2).split(",") if v.strip()]
                self._emit(f"enum {m.group(1)} {{ {', '.join(variants)} }}")
                continue
            # impl blocks → class
            m = re.match(r"impl(?:<[^<>]*>)?\s+(\w+)[^{]*\{", line)
            if m:
                self._emit(f"class {m.group(1)}:")
                self.indent += 1
                self.report.bump("impl→class")
                continue
            # match arms: `PAT => {` or `PAT => expr,`
            m = re.match(r"(.*?=>)\s*(\{)?\s*(.*?)(,)?\s*$", line)
            if m and "=>" in line and not line.startswith("fn "):
                pat = m.group(1)[: -len("=>")].strip()
                pat = re.sub(r"^\}", "", pat).strip() or "_"
                pat = {"_": "_"}.get(pat, pat)
                self._emit(f"case {pat}:")
                if m.group(2):  # brace body
                    self.indent += 1
                    continue
                if m.group(3):
                    self.indent += 1
                    self._emit_line(m.group(3))
                    self.indent -= 1
                continue
            # control-flow headers ending in '{'
            if line.endswith("{"):
                header = line[:-1].strip()
                # `} else {` / `} else if cond {` — the leading `}` closes the
                # previous branch: dedent BEFORE emitting the new header.
                if header.startswith("}"):
                    self.indent = max(0, self.indent - 1)
                    header = header[1:].strip()
                header = re.sub(r"^else\s+if\b", "elif", header)
                header = re.sub(r"^loop\s*$", "while True", header)
                if header.startswith("fn ") or re.match(r"fn\s+\w+", header):
                    header = self._signature(header)
                elif re.match(r"(for|while)\b", header):
                    header = self._types(header)
                    header = re.sub(r"\bin\b", "in", header)
                elif header.startswith("match "):
                    header = self._types(header)
                    self._emit(f"{header}:")
                    self.indent += 1
                    continue
                elif not header.startswith(("if", "elif", "else", "while", "for")):
                    header = self._types(header)
                self._emit(f"{header}:")
                self.indent += 1
                continue
            if line == "}":
                self.indent = max(0, self.indent - 1)
                continue
            if line.startswith("} "):
                self.indent = max(0, self.indent - 1)
                line = line[1:].strip()
                if line.endswith("{"):
                    header = line[:-1].strip()
                    header = re.sub(r"^else\s+if\b", "elif", header)
                    if header.startswith("fn "):
                        header = self._signature(header)
                    self._emit(f"{header}:")
                    self.indent += 1
                    continue
                if line.startswith("fn "):
                    self._emit(self._signature(line[:-1] if line.endswith(":") else line))
                    continue
            if line.startswith("fn "):
                header = line.rstrip("{").strip() if not line.endswith("{") else line[:-1].strip()
                self._emit(self._signature(header) + ":")
                self.indent += 1
                continue
            self._emit_line(line, tail=self._is_tail(i - 1, lines))

        text = "\n".join(self.out) + "\n"
        return text

    def _emit_line(self, line: str, tail: bool = False) -> None:
        if line.endswith(";"):
            line = line[:-1].strip()
        if not line:
            return
        # Rust tail expression: a bare value as the last statement of a block
        # is that block's return value.
        if tail and re.fullmatch(r"[A-Za-z_]\w*(\(.*\))?", line) and not line.startswith(("print", "return")):
            self._emit(f"return {self._types(line)}")
            return
        if line.startswith("return"):
            rest = line[6:].strip()
            self._emit(f"return {self._types(rest)}" if rest else "return")
            return
        if re.match(r"(let|let\s+mut)\b", line):
            self._emit(self._let(line))
            return
        if "!" in line and re.search(r"\b(println|print|eprintln|eprint|format|vec|panic|assert)!", line):
            if "panic!" in line:
                self.report.warn("panic! → raise RuntimeError")
                self._emit(self._types(line).replace("panic!", "raise RuntimeError"))
                return
            self._emit(self._macro(self._types(line)))
            return
        line = self._struct_literal(self._types(line))
        self._emit(line)

    def _emit(self, line: str) -> None:
        self.out.append("    " * self.indent + line if line else "")


def translate_rust(source: str, filename: str = "<source>") -> tuple[str, TranslationReport]:
    """Translate Rust ``source`` into Externum source (pragmatic subset)."""
    conv = _Rs2Ext()
    text = conv.run(source)
    header = "# Translated from Rust by `externum translate` (rs2ext) — heuristic subset"
    return header + "\n\n" + text, conv.report
