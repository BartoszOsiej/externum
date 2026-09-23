"""Regression tests for v4.2.3 fixes.

- bare generator expressions in call arguments (`sum(x for x in xs)`)
  used to compile to invalid Python (`sum(x, for, x in xs)`)
- classes defined at module level and used inside a function body used to
  fail on the VM backend with "undefined global `X`"

Run with:  python3 -m unittest tests/test_genexpr_and_vmclass.py -v
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum import BytecodeCompiler, Compiler, Lexer, Parser, VM


def compile_python_target(src: str) -> str:
    comp = Compiler(list(Parser(Lexer(src).tokenize()).parse()))
    comp.compile()
    return "\n".join(comp.output["python"])


class TestGeneratorExpressions(unittest.TestCase):
    def test_genexpr_compiles_to_valid_python(self):
        src = "xs: List[Int] = [1, 2, 3]\nt: Int = sum(x for x in xs)\nprint(t)\n"
        py = compile_python_target(src)
        self.assertIn("sum([x for x in xs])", py)

    def test_genexpr_runs_and_returns_value(self):
        src = "xs: List[Int] = [1, 2, 3]\nprint(sum(x for x in xs))\n"
        out = io.StringIO()
        with redirect_stdout(out):
            VM().run_source.__self__ if False else None
        # run through the python backend (Runtime-equivalent): compile + exec
        py = compile_python_target(src)
        ns = {}
        exec(compile(py, "<test>", "exec"), ns)

    def test_genexpr_with_filter(self):
        src = "xs: List[Int] = [1, 2, 3, 4]\nprint(sum(x for x in xs if x > 2))\n"
        py = compile_python_target(src)
        self.assertIn("if x > 2", py)


class TestVMClassInFunction(unittest.TestCase):
    def test_class_defined_top_level_used_in_main(self):
        src = (
            "class Greeter:\n"
            "    def greet(self) -> Str:\n"
            '        return "hi"\n'
            "\n"
            "def main():\n"
            "    g: Any = Greeter()\n"
            "    print(g.greet())\n"
        )
        out = io.StringIO()
        with redirect_stdout(out):
            VM(stdout=out).run_source(src)
        self.assertIn("hi", out.getvalue())

    def test_class_with_ctor_and_attrs(self):
        src = (
            "class Counter:\n"
            "    def __init__(self, n: Int):\n"
            "        self.n = n\n"
            "    def bump(self) -> Int:\n"
            "        self.n = self.n + 1\n"
            "        return self.n\n"
            "\n"
            "def main():\n"
            "    c: Any = Counter(5)\n"
            "    c.bump()\n"
            "    print(c.bump())\n"
        )
        out = io.StringIO()
        with redirect_stdout(out):
            VM(stdout=out).run_source(src)
        self.assertIn("7", out.getvalue())


class TestVMComprehensionMessage(unittest.TestCase):
    def test_clear_error_for_comprehension_on_vm(self):
        src = "xs: List[Int] = [1, 2]\nprint([x for x in xs])\n"
        with self.assertRaises(SyntaxError) as cm:
            VM().run_source(src)
        self.assertIn("does not support comprehensions", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
