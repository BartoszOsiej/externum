"""Tests for rich error diagnostics (line numbers, snippets, carets).

Covers the diagnostics upgrade:
1. Real line numbers in the VM line_table (previously everything was line 1).
2. error_location() mapping runtime failures back to source lines.
3. format_runtime_error / format_syntax_error rendering.

Written as unittest.TestCase so both `pytest` and stdlib
`python -m unittest discover` run the full set (CI has no pytest).
"""

import unittest

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


class TestLineTables(unittest.TestCase):
    def test_module_line_table_has_real_lines(self):
        module = compile_src("x = 1\ny = 2\nz = 3\n")
        lines = sorted(set(module.line_table.values()))
        self.assertEqual(lines, [1, 2, 3])

    def test_function_line_table_has_real_lines(self):
        module = compile_src(
            "def f(a):\n"
            "    b = a + 1\n"
            "    return b\n"
            "\n"
            "f(1)\n"
        )
        fn = next(f for f in module.functions if f.name == "f")
        lines = sorted(set(fn.line_table.values()))
        self.assertIn(2, lines)
        self.assertIn(3, lines)

    def test_ast_nodes_carry_line_numbers(self):
        ast = list(Parser(Lexer("x = 1\ny = 2\n").tokenize()).parse())
        self.assertEqual([node.line for node in ast], [1, 2])


class TestErrorLocation(unittest.TestCase):
    def test_vm_error_location_index_error(self):
        src = 'x = [1, 2, 3]\nprint("before")\nprint(x[10])\n'
        vm = VM()
        with self.assertRaises(IndexError):
            vm.run_module(compile_src(src))
        line, _col = vm.error_location()
        self.assertEqual(line, 3)

    def test_vm_error_location_unwinds_to_call_site_or_body(self):
        src = (
            "def divide(a, b):\n"
            "    return a / b\n"
            "\n"
            "print(divide(10, 0))\n"
        )
        vm = VM()
        with self.assertRaises(ZeroDivisionError):
            vm.run_module(compile_src(src))
        line, _col = vm.error_location()
        self.assertIn(line, (2, 4))

    def test_error_location_without_error_is_safe(self):
        vm = VM()
        line, col = vm.error_location()
        self.assertEqual((line, col), (0, 0))


class TestFormatting(unittest.TestCase):
    def test_format_runtime_error_renders_snippet(self):
        src = 'x = [1]\nprint("ok")\nprint(x[10])\n'
        out = format_runtime_error(IndexError("list index out of range"), src, "t.ext", 3, 1)
        self.assertIn("Runtime Error: list index out of range", out)
        self.assertIn("--> t.ext:3:1", out)
        self.assertIn(">  3 | print(x[10])", out)
        self.assertIn("^", out)

    def test_format_runtime_error_without_location(self):
        out = format_runtime_error(ValueError("boom"), "x = 1\n", "t.ext", None)
        self.assertEqual(out, "Runtime Error: boom")

    def test_format_syntax_error_uses_exc_text(self):
        exc = SyntaxError("invalid syntax", ("t.ext", 2, 1, "print(x)\n"))
        out = format_syntax_error(exc, "x = (1 +\nprint(x)\n", "t.ext")
        self.assertIn("Syntax Error: invalid syntax", out)
        self.assertIn("--> t.ext:2:1", out)
        self.assertIn(">  2 | print(x)", out)

    def test_source_map_nearest_line(self):
        sm = SourceMap({0: 1, 10: 2, 40: 3})
        self.assertEqual(sm.line_at(0), 1)
        self.assertEqual(sm.line_at(5), 1)
        self.assertEqual(sm.line_at(10), 2)
        self.assertEqual(sm.line_at(999), 3)  # clamps to last entry
        self.assertEqual(SourceMap({}).line_at(5), 0)


class TestLexerPositions(unittest.TestCase):
    def test_lexer_error_carries_position(self):
        with self.assertRaises(SyntaxError) as ctx:
            Lexer("x = 5 $ 3\n").tokenize()
        self.assertEqual(ctx.exception.lineno, 1)
        self.assertEqual(ctx.exception.offset, 7)  # '$' is the 7th char (1-based)
        self.assertIsNotNone(ctx.exception.text)


class TestNoRegression(unittest.TestCase):
    def test_good_programs_still_run(self):
        """Diagnostics instrumentation must not break normal execution."""
        vm = VM()
        result = vm.run_source("x = 21\nprint(x * 2)\n")
        self.assertIsNone(result)  # print returns None; no exception is the point


if __name__ == "__main__":
    unittest.main()
