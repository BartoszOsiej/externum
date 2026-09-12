"""Rich error diagnostics for Externum — line numbers, code snippets, carets.

Every user-facing failure (parse-time SyntaxError and VM runtime errors)
flows through :func:`format_syntax_error` / :func:`format_runtime_error`,
so the CLI prints

    Runtime Error: list index out of range
      --> examples/pokedex.ext:3:9
         1 | x = [1, 2, 3]
      >  3 | print(x[10])
           |         ^

instead of a bare one-liner.
"""

from __future__ import annotations

import re

_LINES_RE = re.compile(r"[^\n]*(?:\n|$)")


def _source_lines(source: str) -> list[str]:
    """Split source into lines (1-based indexing handled by callers)."""
    return _LINES_RE.findall(source) or [""]


def _line_of(source: str, line_no: int) -> str:
    lines = _source_lines(source)
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].rstrip("\n")
    return ""


def _col_of(source: str, line_no: int, col_no: int | None) -> int:
    """Sanitize a column; default to 1."""
    if col_no is None or col_no < 1:
        return 1
    line = _line_of(source, line_no)
    return min(col_no, max(1, len(line)) + 1)


def format_syntax_error(
    exc: SyntaxError,
    source: str,
    filename: str = "<source>",
) -> str:
    """Format a SyntaxError with a code snippet and caret."""
    line_no = exc.lineno or 1
    col = _col_of(source, line_no, exc.offset)
    text = exc.text or _line_of(source, line_no)
    if text is None:
        text = _line_of(source, line_no)
    text = (text or "").rstrip("\n")

    lines = [
        f"Syntax Error: {exc.msg}",
        f"  --> {filename}:{line_no}:{col}",
    ]
    lines.extend(_render_snippet(source, line_no, col, text))
    if exc.msg and exc.msg not in text:
        lines.append(f"   note: {exc.msg}")
    return "\n".join(lines)


def format_runtime_error(
    exc: BaseException,
    source: str,
    filename: str = "<source>",
    line_no: int | None = None,
    col_no: int | None = None,
) -> str:
    """Format a runtime error with location + snippet (location optional)."""
    header = f"Runtime Error: {exc}"
    if line_no is None:
        return header
    col = _col_of(source, line_no, col_no)
    lines = [
        header,
        f"  --> {filename}:{line_no}:{col}",
    ]
    lines.extend(_render_snippet(source, line_no, col))
    return "\n".join(lines)


def _render_snippet(
    source: str,
    line_no: int,
    col: int,
    text_override: str | None = None,
    context: int = 1,
) -> list[str]:
    """Gutter-rendered snippet: `>` marks the error line, `^` the column."""
    text = text_override if text_override is not None else _line_of(source, line_no)
    gutter_w = max(2, len(str(line_no + context)))
    out = []

    start = max(1, line_no - context)
    end = line_no + context
    src_lines = _source_lines(source)
    for ln in range(start, min(end, len(src_lines)) + 1):
        content = src_lines[ln - 1].rstrip("\n")
        marker = ">" if ln == line_no else " "
        out.append(f"  {marker} {ln:>{gutter_w}} | {content}")
        if ln == line_no:
            caret_col = min(max(1, col), len(content) + 1)
            pad = " " * (caret_col - 1)
            out.append(f"    {' ' * gutter_w} | {pad}^")
    return out


# ---------------------------------------------------------------- helpers used by the VM


class SourceMap:
    """bytecode offset -> (line, col) for one compiled unit."""

    __slots__ = ("_table",)

    def __init__(self, table: dict[int, int] | None = None):
        self._table: dict[int, int] = dict(table or {})

    def line_at(self, offset: int) -> int:
        """Nearest recorded line at or before `offset` (binary search)."""
        if not self._table:
            return 0
        offsets = sorted(self._table)
        lo, hi = 0, len(offsets) - 1
        best = offsets[0]
        while lo <= hi:
            mid = (lo + hi) // 2
            if offsets[mid] <= offset:
                best = offsets[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return self._table[best]

    def col_at(self, offset: int) -> int:
        return 1  # columns are not tracked yet; line is the win


def annotate_location(
    source: str,
    filename: str,
    line_no: int,
    col_no: int,
) -> str:
    """One-line location string: 'file.ext:LINE:COL'."""
    col = _col_of(source, line_no, col_no)
    return f"{filename}:{line_no}:{col}"
