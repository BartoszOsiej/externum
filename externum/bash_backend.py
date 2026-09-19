"""Externum v4.2 — real Bash backend.

Translates a subset of Externum into a standalone Bash script:

- module-level control flow (``while``/``for``/``if``/``elif``/``else``,
  ``break``/``continue``), integer arithmetic via ``$(( ))``, string literals,
  ``print``, embedded ``bash { ... }`` blocks verbatim
- functions (``def``/``fn``): positional params bound with ``local``,
  default params via ``${N:-default}``, ``return <expr>`` emitted as
  ``printf`` + ``return 0`` and captured through ``$( )`` — recursion works
  because every local is dynamically scoped per invocation

Programs using features the backend does not support still compile: the
unsupported statements are skipped and reported as warnings, so
``--target bash`` never silently produces an empty script again
(follow-up to issues #19/#20).
"""

from __future__ import annotations

import re

from .parser import ASTNode

_ARITH_OPS = {"+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "**": "**", "//": "/"}
_CMP_OPS = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class BashCodegen:
    """AST → Bash. Functions compile to real bash functions; unsupported constructs warn."""

    def __init__(self, ast: list[ASTNode]):
        self.ast = ast
        self.lines: list[str] = []
        self.warnings: list[str] = []
        self.indent = 0
        self.fn_returns: dict[str, bool] = {}
        self.in_function: str | None = None
        self.locals_declared: set[str] = set()

    def generate(self) -> tuple[str, list[str]]:
        self.lines.append("#!/usr/bin/env bash")
        self.lines.append("set -euo pipefail")
        for node in self.ast:
            self._stmt(node)
        return "\n".join(self.lines) + "\n", self.warnings

    # ── statements ──────────────────────────────────────────────────
    def _stmt(self, node: ASTNode | None):
        if node is None:
            return
        t = node.type
        if t in ("NEWLINE", "INDENT", "DEDENT", "OP", "UNKNOWN"):
            # UNKNOWN nodes are parser artifacts (e.g. the bare `else:` token
            # left as an ELSE child); the Python transpiler skips them too.
            return
        method = getattr(self, f"_s_{t}", None)
        if method:
            method(node)
        else:
            self._warn(node, "statement not supported by the bash backend")

    def _warn(self, node: ASTNode | None, what: str):
        line = getattr(node, "line", 0) if node is not None else 0
        self.warnings.append(f"bash backend: line {line or '?'}: {what}")

    def _emit(self, s: str):
        self.lines.append("    " * self.indent + s)

    # ── functions ───────────────────────────────────────────────────
    def _s_FUNCTION(self, node: ASTNode):
        name = str(node.value)
        params_node = None
        body = list(node.children)
        if node.children and node.children[0].type == "PARAMS":
            params_node = node.children[0]
            body = node.children[1:]
        params = self._parse_params(params_node)
        if params is None:
            self._warn(node, f"parameters of function {name!r} not supported by the bash backend")
            return
        returns_value = self._scan_returns_value(body)
        if returns_value and self._scan_prints(body):
            self.warnings.append(
                f"bash backend: function {name!r} both prints to stdout and returns a value; "
                "print output mixes into the captured result"
            )
        self.fn_returns[name] = returns_value
        self._emit(f"{name}() {{")
        self.indent += 1
        old_fn, old_locals = self.in_function, self.locals_declared
        self.in_function = name
        self.locals_declared = {p for p, _ in params}
        for i, (pname, default) in enumerate(params, start=1):
            if default is None:
                self._emit("local " + pname + '="${' + str(i) + '}"')
            else:
                self._emit(f'local {pname}="${{{i}:-{default}}}"')
        for stmt in body:
            self._stmt(stmt)
        self.indent -= 1
        self._emit("}")
        self.lines.append("")
        self.in_function, self.locals_declared = old_fn, old_locals

    def _parse_params(self, params_node: ASTNode | None) -> list[tuple[str, str | None]] | None:
        """Parse PARAMS into [(name, default_or_None)]. None = unsupported."""
        if params_node is None:
            return []
        raw = str(params_node.value or "").strip()
        if not raw:
            return []
        # top-level comma split (respects brackets)
        depth, current, items = 0, [], []
        for ch in raw:
            if ch in "([{":
                depth += 1
                current.append(ch)
            elif ch in ")]}":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                items.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            items.append("".join(current))
        params: list[tuple[str, str | None]] = []
        for item in items:
            item = item.strip()
            if not item:
                continue
            pname, default = item, None
            if "=" in item:
                pname, _, dflt = item.partition("=")
                pname, default = pname.strip(), dflt.strip()
            pname = pname.split(":")[0].strip()  # tolerate annotations
            if not _IDENT_RE.fullmatch(pname):
                return None
            if default is not None:
                rendered = self._render_default(default)
                if rendered is None:
                    self._warn(params_node, f"default for {pname!r} not supported by the bash backend")
                params.append((pname, rendered))
            else:
                params.append((pname, None))
        return params

    def _render_default(self, dflt: str) -> str | None:
        """Render a parameter default for use inside ${N:-...} (double-quoted)."""
        try:
            int(dflt)
            return dflt
        except ValueError:
            pass
        if len(dflt) >= 2 and dflt[0] == dflt[-1] and dflt[0] in "\"'":
            inner = dflt[1:-1]
            # safe inside "${N:-...}": no quote/brace/expansion metacharacters
            if inner and not re.search(r'["\'\\$`{}]', inner):
                return inner
        return None

    def _scan_returns_value(self, nodes: list[ASTNode]) -> bool:
        for n in nodes:
            if n is None:
                continue
            if n.type == "RETURN" and n.children:
                return True
            if n.type == "FUNCTION":
                continue  # nested defs own their returns
            if self._scan_returns_value(list(n.children)):
                return True
        return False

    def _scan_prints(self, nodes: list[ASTNode]) -> bool:
        for n in nodes:
            if n is None:
                continue
            if n.type == "CALL" and str(n.value) == "print":
                return True
            if n.type == "FUNCTION":
                continue
            if self._scan_prints(list(n.children)):
                return True
        return False

    # ── simple statements ───────────────────────────────────────────
    def _s_ASSIGN(self, node: ASTNode):
        tgt = node.children[0] if node.children else None
        rhs = node.children[1] if len(node.children) > 1 else None
        if tgt is not None and tgt.type == "IDENTIFIER":
            self._assign_to(tgt.value, rhs, node)
        else:
            self._warn(node, "assignment target not supported by the bash backend")

    def _s_DECLARE(self, node: ASTNode):
        # Defensive: the parser normally folds `mut x: Int = 0` into ASSIGN.
        name = str(node.value or "").split(":")[0].split("=")[0].strip()
        rhs = node.children[0] if node.children else None
        if _IDENT_RE.fullmatch(name):
            self._assign_to(name, rhs, node)
        else:
            self._warn(node, "declaration not supported by the bash backend")

    def _s_AUG_ASSIGN(self, node: ASTNode):
        tgt = node.children[0] if node.children else None
        val = node.children[1] if len(node.children) > 1 else None
        op_node = node.children[2] if len(node.children) > 2 else None
        base = str(op_node.value).rstrip("=") if op_node is not None else "+"
        if tgt is not None and tgt.type == "IDENTIFIER" and base in _ARITH_OPS:
            rhs = self._arith(val)
            if rhs is not None:
                # augmented assignment implies the variable already exists —
                # never introduce a `local` here (module globals stay global)
                self._emit(f"{tgt.value}=$(( {tgt.value} {_ARITH_OPS[base]} {rhs} ))")
                return
        self._warn(node, "augmented assignment not supported by the bash backend")

    def _assign_to(self, name: str, rhs: ASTNode | None, node: ASTNode):
        kw = ""
        if self.in_function is not None and name not in self.locals_declared:
            kw = "local "
            self.locals_declared.add(name)
        a = self._arith(rhs)
        if a is not None:
            self._emit(f"{kw}{name}=$(( {a} ))")
            return
        if rhs is not None and rhs.type == "STRING":
            inner = self._string_value(rhs)
            if inner is not None:
                self._emit(f"{kw}{name}={self._shq(inner)}")
                return
        w = self._word(rhs)
        if w is not None:
            self._emit(f"{kw}{name}={w}")
            return
        self._warn(node, "value not supported by the bash backend")

    # ── control flow ────────────────────────────────────────────────
    def _s_IF(self, node: ASTNode):
        cond = self._cond(node.children[0] if node.children else None)
        if cond is None:
            self._warn(node, "if condition not supported by the bash backend")
            return
        self._emit(f"if {cond}; then")
        self.indent += 1
        for child in node.children[1:]:
            if child.type in ("ELIF", "ELSE"):
                break
            self._stmt(child)
        self.indent -= 1
        for child in node.children[1:]:
            if child.type == "ELIF":
                c = self._cond(child.children[0] if child.children else None)
                if c is None:
                    self._warn(child, "elif condition not supported by the bash backend")
                    return
                self._emit(f"elif {c}; then")
                self.indent += 1
                for sub in child.children[1:]:
                    if sub.type in ("ELIF", "ELSE"):
                        break
                    self._stmt(sub)
                self.indent -= 1
            elif child.type == "ELSE":
                self._emit("else")
                self.indent += 1
                for sub in child.children:
                    self._stmt(sub)
                self.indent -= 1
        self._emit("fi")

    def _s_WHILE(self, node: ASTNode):
        cond = self._cond(node.children[0] if node.children else None)
        if cond is None:
            self._warn(node, "while condition not supported by the bash backend")
            return
        self._emit(f"while {cond}; do")
        self.indent += 1
        for child in node.children[1:]:
            self._stmt(child)
        self.indent -= 1
        self._emit("done")

    def _s_FOR(self, node: ASTNode):
        var = node.value or "_"
        body = node.children
        it: ASTNode | None = None
        if node.children and node.children[0].type == "ITERABLE":
            inner = node.children[0].children
            it = inner[0] if inner else None
            body = node.children[1:]

        if it is not None and it.type == "CALL" and it.value == "range":
            args = [self._arith(a) for a in it.children]
            if len(args) == 1 and args[0]:
                self._emit(f"for (( {var} = 0; {var} < {args[0]}; {var}++ )); do")
            elif len(args) == 2 and all(args):
                self._emit(f"for (( {var} = {args[0]}; {var} < {args[1]}; {var}++ )); do")
            elif len(args) == 3 and all(args):
                self._emit(f"for (( {var} = {args[0]}; {var} < {args[1]}; {var} += {args[2]} )); do")
            else:
                self._warn(node, "range() arguments not supported by the bash backend")
                return
        elif it is not None:
            items = self._list_items(it)
            if items is None:
                self._warn(node, "iterable not supported by the bash backend")
                return
            self._emit(f"for {var} in {items}; do")
        else:
            self._emit(f'for {var} in "$@"; do')

        self.indent += 1
        for child in body:
            self._stmt(child)
        self.indent -= 1
        self._emit("done")

    def _s_BREAK(self, node: ASTNode):
        self._emit("break")

    def _s_CONTINUE(self, node: ASTNode):
        self._emit("continue")

    def _s_PASS(self, node: ASTNode):
        self._emit(":")

    def _s_RETURN(self, node: ASTNode):
        if self.in_function is None:
            self._warn(node, "return outside a function is not supported by the bash backend")
            return
        val = node.children[0] if node.children else None
        if val is None:
            self._emit("return 0")
            return
        w = self._word(val)
        if w is None:
            self._warn(node, "return value not supported by the bash backend")
            self._emit("return 0")
            return
        arg = w if w.startswith(("'", '"')) else f'"{w}"'
        self._emit(f"printf '%s\\n' {arg}")
        self._emit("return 0")

    # ── calls / print ───────────────────────────────────────────────
    def _s_EXPRESSION(self, node: ASTNode):
        self._warn(node, "expression statement not supported by the bash backend")

    def _s_CALL(self, node: ASTNode):
        if node.value == "print":
            self._echo(node)
            return
        call = self._call_expr(node, value_ctx=False)
        if call is None:
            self._warn(node, f"call to {node.value!r}() not supported by the bash backend")
            return
        if self.fn_returns.get(str(node.value)):
            # bare call discards the value — matches the Python target
            self._emit(f"{call} > /dev/null")
        else:
            self._emit(call)

    def _s_BASH_BLOCK(self, node: ASTNode):
        self._emit(str(node.value).strip())

    def _s_BASH_COMMAND(self, node: ASTNode):
        self._emit(" ".join(c.value for c in node.children if hasattr(c, "value")))

    def _call_expr(self, node: ASTNode, value_ctx: bool) -> str | None:
        fn = str(node.value)
        if fn == "print":
            return None
        args = []
        for c in node.children:
            w = self._quoted_word(c)
            if w is None:
                return None
            args.append(w)
        joined = (" " + " ".join(args)) if args else ""
        return f"$( {fn}{joined} )" if value_ctx else f"{fn}{joined}"

    def _echo(self, call: ASTNode):
        parts = []
        for c in call.children:
            w = self._word(c)
            if w is None:
                self._warn(call, "print argument not supported by the bash backend")
                return
            parts.append(w)
        self._emit("echo " + " ".join(parts) if parts else "echo")

    # ── words (single shell words: echo / [[ ]] / args) ─────────────
    def _word(self, node: ASTNode | None) -> str | None:
        """Render an expression as one shell word (quoted expansions included)."""
        if node is None:
            return None
        t = node.type
        if t == "NUMBER":
            return str(node.value) if isinstance(node.value, int) else None
        if t == "STRING":
            inner = self._string_value(node)
            return self._shq(inner) if inner is not None else None
        if t == "IDENTIFIER":
            if node.value in ("True", "False", "None"):
                return None
            return '"${' + node.value + '}"' if _IDENT_RE.fullmatch(node.value) else None
        if t == "CALL":
            sub = self._call_expr(node, value_ctx=True)
            return f'"{sub}"' if sub is not None else None
        if t == "BINOP":
            opn = node.children[1] if len(node.children) > 1 else None
            op = str(opn.value) if opn is not None else ""
            if op == "+":
                # string concatenation: s + "!" → "${s}!"
                parts = []
                for ch in (node.children[0], node.children[2]):
                    piece = self._concat_piece(ch)
                    if piece is None:
                        break
                    parts.append(piece)
                if len(parts) == 2:
                    return '"' + "".join(parts) + '"'
            a = self._arith(node)
            return f'"$(( {a} ))"' if a is not None else None
        if t == "UNARYOP":
            a = self._arith(node)
            return f'"$(( {a} ))"' if a is not None else None
        a = self._arith(node)
        if a is not None:
            return f'"$(( {a} ))"'
        return None

    def _concat_piece(self, node: ASTNode | None) -> str | None:
        """One piece of a double-quoted string-concat word, or None.

        Recurses into left-associative ``+`` chains: ("a" + b) + "c" flattens
        to three pieces inside one double-quoted word.
        """
        if node is None:
            return None
        if node.type == "BINOP":
            opn = node.children[1] if len(node.children) > 1 else None
            if opn is not None and str(opn.value) == "+":
                left = self._concat_piece(node.children[0] if node.children else None)
                right = self._concat_piece(node.children[2] if len(node.children) > 2 else None)
                if left is not None and right is not None:
                    return left + right
                return None
        if node.type == "STRING":
            inner = self._string_value(node)
            if inner is None:
                return None
            return inner.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        if node.type == "IDENTIFIER" and node.value not in ("True", "False", "None"):
            return "${" + node.value + "}" if _IDENT_RE.fullmatch(node.value) else None
        return None

    def _quoted_word(self, node: ASTNode | None) -> str | None:
        """_word result guaranteed to be a single safely-quoted word."""
        w = self._word(node)
        if w is None:
            return None
        if w.startswith(("'", '"')):
            return w
        return f'"{w}"'

    def _list_items(self, node: ASTNode) -> str | None:
        """Render a list/tuple literal as bash word-list items."""
        val = str(node.value)
        if not (val.startswith("[") and val.endswith("]")) and not (val.startswith("(") and val.endswith(")")):
            return None
        inner = val[1:-1].strip()
        if not inner:
            return ""
        parts = []
        for chunk in inner.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                parts.append(str(int(chunk)))
                continue
            except ValueError:
                pass
            if len(chunk) >= 2 and chunk[0] == chunk[-1] and chunk[0] in "\"'":
                parts.append(self._shq(chunk[1:-1]))
                continue
            return None
        return " ".join(parts)

    # ── expressions ─────────────────────────────────────────────────
    def _shq(self, s: str) -> str:
        return "'" + str(s).replace("'", "'\\''") + "'"

    def _string_value(self, node: ASTNode) -> str | None:
        v = node.value
        if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            return v[1:-1]
        return None

    def _cond(self, node: ASTNode | None) -> str | None:
        a = self._arith(node)
        if a is not None:
            return f"(( {a} ))"
        # string (in)equality via [[ ]]
        if node is not None and node.type == "BINOP":
            opn = node.children[1] if len(node.children) > 1 else None
            op = str(opn.value) if opn is not None else ""
            if op in ("==", "!="):
                lhs = self._word(node.children[0]) if node.children else None
                rhs = self._word(node.children[2]) if len(node.children) > 2 else None
                if lhs is not None and rhs is not None:
                    return f"[[ {lhs} {op} {rhs} ]]"
        return None

    def _arith(self, node: ASTNode | None) -> str | None:
        """Render an expression for use inside $(( ... )). None = unsupported."""
        if node is None:
            return None
        t = node.type
        if t == "NUMBER":
            return str(node.value) if isinstance(node.value, int) else None
        if t in ("BINARY_NUMBER", "HEX_NUMBER", "OCTAL_NUMBER"):
            return str(int(node.value))
        if t == "IDENTIFIER":
            if node.value in ("True", "False", "None"):
                return None
            return node.value if _IDENT_RE.fullmatch(node.value) else None
        if t == "CALL":
            sub = self._call_expr(node, value_ctx=True)
            return f"( {sub} )" if sub is not None else None
        if t == "BINOP":
            opn = node.children[1] if len(node.children) > 1 else None
            op = str(opn.value) if opn is not None else None
            lhs = self._arith(node.children[0]) if node.children else None
            rhs = self._arith(node.children[2]) if len(node.children) > 2 else None
            if lhs is None or rhs is None or op is None:
                return None
            if op in _ARITH_OPS:
                return f"({lhs} {_ARITH_OPS[op]} {rhs})"
            if op in _CMP_OPS:
                return f"({lhs} {_CMP_OPS[op]} {rhs})"
            if op == "and":
                return f"({lhs} && {rhs})"
            if op == "or":
                return f"({lhs} || {rhs})"
            return None
        if t == "UNARYOP":
            opn = node.children[0] if node.children else None
            operand = node.children[1] if len(node.children) > 1 else None
            inner = self._arith(operand)
            if inner is None:
                return None
            op = str(opn.value) if opn is not None else "-"
            if op == "-":
                return f"(-{inner})"
            if op == "+":
                return f"({inner})"
            if op == "not":
                return f"(! {inner})"
            return None
        if t == "EXPRESSION":
            # Raw source text (e.g. parenthesized sub-expressions): re-parse
            # through the real parser and translate the resulting tree.
            text = str(node.value).strip()
            from .lexer import Lexer
            from .parser import Parser

            try:
                sub = list(Parser(Lexer(text).tokenize()).parse())
            except Exception:
                return None
            if len(sub) != 1:
                return None
            only = sub[0]
            if only.type == "EXPRESSION" and str(only.value).strip() == text:
                return None  # parser made no progress — give up, avoid recursion
            return self._arith(only)
        return None
