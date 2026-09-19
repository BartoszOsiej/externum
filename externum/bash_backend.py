"""Externum v4.2 — real Bash backend.

Translates a subset of Externum (module-level control flow, integer
arithmetic, string literals, ``print``) into a standalone Bash script.
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
    """AST → Bash. Module-level statements only; functions are not supported."""

    def __init__(self, ast: list[ASTNode]):
        self.ast = ast
        self.lines: list[str] = []
        self.warnings: list[str] = []
        self.indent = 0

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
                self._emit(f"{tgt.value}=$(( {tgt.value} {_ARITH_OPS[base]} {rhs} ))")
                return
        self._warn(node, "augmented assignment not supported by the bash backend")

    def _assign_to(self, name: str, rhs: ASTNode | None, node: ASTNode):
        a = self._arith(rhs)
        if a is not None:
            self._emit(f"{name}=$(( {a} ))")
            return
        if rhs is not None and rhs.type == "STRING":
            inner = self._string_value(rhs)
            if inner is not None:
                self._emit(f"{name}={self._shq(inner)}")
                return
        self._warn(node, "value not supported by the bash backend")

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
        self._warn(node, "return outside a function is not supported by the bash backend")

    def _s_EXPRESSION(self, node: ASTNode):
        self._warn(node, "expression statement not supported by the bash backend")

    def _s_CALL(self, node: ASTNode):
        if node.value == "print":
            self._echo(node)
        else:
            self._warn(node, f"call to {node.value!r}() not supported by the bash backend")

    def _s_BASH_BLOCK(self, node: ASTNode):
        self._emit(str(node.value).strip())

    def _s_BASH_COMMAND(self, node: ASTNode):
        self._emit(" ".join(c.value for c in node.children if hasattr(c, "value")))

    # ── print / words ───────────────────────────────────────────────
    def _echo(self, call: ASTNode):
        parts = []
        for c in call.children:
            w = self._word(c)
            if w is None:
                self._warn(call, "print argument not supported by the bash backend")
                return
            parts.append(w)
        self._emit("echo " + " ".join(parts) if parts else "echo")

    def _word(self, node: ASTNode | None) -> str | None:
        """Render an expression as one shell word (echo / [[ ]] context)."""
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
            return "${" + node.value + "}" if _IDENT_RE.fullmatch(node.value) else None
        a = self._arith(node)
        if a is not None:
            return "$(( " + a + " ))"
        return None

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
