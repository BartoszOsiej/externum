"""Tests for rich error diagnostics (line numbers, snippets, carets).

Covers the three pillars added in the diagnostics upgrade:
1. Real line numbers in the VM line_table (previously everything was line 1).
2. error_location() mapping runtime failures back to source lines.
3. format_runtime_error / format_syntax_error rendering.
"""

import pytest

from externum.bytecode import BytecodeCompiler
from externum.diagnostics import (
    SourceMap,
    format_runtime_error,
    format_syntax_error,
)
from externum.lexer import Lexer
from externum.parser import Parser
from externum.vm import VM


def compile_src(source: str, name: str = "<test>"):
    ast = list(Parser(Lexer(source).tokenize()).parse())
    return BytecodeCompiler(ast, module_name=name).compile()


# ------------------------------------------------------------------ line tables

def test_module_line_table_has_real_lines():
    module = compile_src("x = 1\ny = 2\nz = 3\n")
    lines = sorted(set(module.line_table.values()))
    assert lines == [1, 2, 3], f"expected lines 1..3, got {lines}"


def test_function_line_table_has_real_lines():
    module = compile_src(
        "def f(a):\n"
        "    b = a + 1\n"
        "    return b\n"
        "\n"
        "f(1)\n"
    )
    fn = next(f for f in module.functions if f.name == "f")
    lines = sorted(set(fn.line_table.values()))
    assert 2 in lines and 3 in lines, f"function body lines missing: {lines}"


def test_ast_nodes_carry_line_numbers():
    ast = list(Parser(Lexer("x = 1\ny = 2\n").tokenize()).parse())
    assert [node.line for node in ast] == [1, 2]


# ------------------------------------------------------------ error location

def test_vm_error_location_index_error():
    src = 'x = [1, 2, 3]\nprint("before")\nprint(x[10])\n'
    vm = VM()
    with pytest.raises(IndexError):
        vm.run_module(compile_src(src))
    line, _col = vm.error_location()
    assert line == 3, f"expected line 3, got {line}"


def test_vm_error_location_zero_division_in_function():
    """Error unwinds from a function: VM reports the failing source line
    inside the function when known, otherwise the call site."""
    src = (
        "def divide(a, b):\n"
        "    return a / b\n"
        "\n"
        "print(divide(10, 0))\n"
    )
    vm = VM()
    with pytest.raises(ZeroDivisionError):
        vm.run_module(compile_src(src))
    line, _col = vm.error_location()
    assert line in (2, 4), f"expected line 2 (inside divide) or 4 (call site), got {line}"


def test_error_location_without_error_is_safe():
    """error_location() works even when nothing failed (no crash)."""
    vm = VM()
    line, col = vm.error_location()
    assert line == 0 and col == 0


# ------------------------------------------------------------- formatting

def test_format_runtime_error_renders_snippet():
    src = 'x = [1]\nprint("ok")\nprint(x[10])\n'
    out = format_runtime_error(IndexError("list index out of range"), src, "t.ext", 3, 1)
    assert "Runtime Error: list index out of range" in out
    assert "--> t.ext:3:1" in out
    assert ">  3 | print(x[10])" in out
    assert "^" in out


def test_format_runtime_error_without_location():
    out = format_runtime_error(ValueError("boom"), "x = 1\n", "t.ext", None)
    assert out == "Runtime Error: boom"


def test_format_syntax_error_uses_exc_text():
    exc = SyntaxError("invalid syntax", ("t.ext", 2, 1, "print(x)\n"))
    out = format_syntax_error(exc, "x = (1 +\nprint(x)\n", "t.ext")
    assert "Syntax Error: invalid syntax" in out
    assert "--> t.ext:2:1" in out
    assert ">  2 | print(x)" in out


def test_source_map_nearest_line():
    sm = SourceMap({0: 1, 10: 2, 40: 3})
    assert sm.line_at(0) == 1
    assert sm.line_at(5) == 1
    assert sm.line_at(10) == 2
    assert sm.line_at(999) == 3  # clamps to last entry
    assert SourceMap({}).line_at(5) == 0


def test_lexer_error_carries_position():
    with pytest.raises(SyntaxError) as excinfo:
        Lexer("x = 5 $ 3\n").tokenize()
    assert excinfo.value.lineno == 1
    assert excinfo.value.offset == 7  # '$' is the 7th char (1-based)
    assert excinfo.value.text is not None


def test_good_programs_still_run():
    """Diagnostics instrumentation must not break normal execution."""
    vm = VM()
    result = vm.run_source("x = 21\nprint(x * 2)\n")
    assert result is None  # print returns None; no exception is the point
