"""Regression tests for Externum v3 additions."""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum import Lexer, Parser, Compiler, Runtime  # noqa: E402


def run_capture(source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        Runtime().run(source)
    return out.getvalue()


class TestMultilineLiterals(unittest.TestCase):
    def test_multiline_list(self):
        out = run_capture(
            "data = [\n"
            "    1,\n"
            "    2,\n"
            "    3,\n"
            "]\n"
            "print(len(data))\n"
            "print(data[1])\n"
        )
        self.assertEqual(out.split(), ["3", "2"])

    def test_multiline_list_calls(self):
        out = run_capture(
            "def f(x):\n    return x * 2\n"
            "data = [\n"
            "    f(1),\n"
            "    f(2),\n"
            "]\n"
            "print(data)\n"
        )
        self.assertIn("[2, 4]", out)

    def test_multiline_dict(self):
        out = run_capture(
            "d = {\n"
            '    "a": 1,\n'
            '    "b": 2,\n'
            "}\n"
            "print(d[\"a\"] + d[\"b\"])\n"
        )
        self.assertIn("3", out)

    def test_multiline_call(self):
        out = run_capture(
            "def f(a, b, c):\n    return a + b + c\n"
            "print(f(\n"
            "    1,\n"
            "    2,\n"
            "    3,\n"
            "))\n"
        )
        self.assertIn("6", out)

    def test_multiline_nested(self):
        out = run_capture(
            "matrix = [\n"
            "    [1, 2],\n"
            "    [3, 4],\n"
            "]\n"
            "print(matrix[1][0])\n"
        )
        self.assertIn("3", out)


class TestClassesWithBlankLines(unittest.TestCase):
    def test_methods_inside_class(self):
        out = run_capture(
            "class Greeter:\n"
            "\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "\n"
            "    def hello(self):\n"
            "        print(\"hi \" + self.name)\n"
            "\n"
            "    def bye(self):\n"
            "        print(\"bye \" + self.name)\n"
            "\n"
            "g = Greeter(\"Kot\")\n"
            "g.hello()\n"
            "g.bye()\n"
        )
        self.assertEqual(out.split(), ["hi", "Kot", "bye", "Kot"])

    def test_inherited_method_call(self):
        out = run_capture(
            "class Base:\n"
            "    def greet(self):\n"
            "        return \"hello\"\n"
            "\n"
            "class Child(Base):\n"
            "    def shout(self):\n"
            "        return self.greet().upper()\n"
            "\n"
            "c = Child()\n"
            "print(c.shout())\n"
        )
        self.assertIn("HELLO", out)


class TestTernaryAndUnpacking(unittest.TestCase):
    def test_ternary_expression(self):
        self.assertEqual(run_capture("print(1 if True else 2)\n"), "1\n")
        self.assertEqual(run_capture("print(1 if False else 2)\n"), "2\n")
        self.assertEqual(run_capture("print('a' if 3 > 2 else 'b')\n"), "a\n")

    def test_tuple_unpacking_swap(self):
        out = run_capture("a, b = 1, 2\na, b = b, a\nprint(a, b)\n")
        self.assertIn("2 1", out)


class TestMoreFeatures(unittest.TestCase):
    def test_multiple_assignment_style(self):
        out = run_capture("a, b = 1, 2\nprint(a + b)\n")
        self.assertIn("3", out)

    def test_nested_lambdas(self):
        out = run_capture(
            "add = lambda a: lambda b: a + b\nprint(add(3)(4))\n"
        )
        self.assertIn("7", out)

    def test_dict_comprehension_like(self):
        out = run_capture(
            "names = [\"ala\", \"ola\"]\n"
            "caps = {n: n.upper() for n in names}\n"
            "print(caps[\"ala\"])\n"
        )
        self.assertIn("ALA", out)

    def test_chain_methods(self):
        out = run_capture(
            's = "  a,b,c  "\n'
            "print(s.strip().replace(\"a\", \"x\").split(\",\"))\n"
        )
        self.assertIn("['x', 'b', 'c']", out)

    def test_string_multiply(self):
        out = run_capture('print(\"ab\" * 3)\n')
        self.assertIn("ababab", out)

    def test_list_methods(self):
        out = run_capture(
            "a = [3, 1, 2]\n"
            "a.reverse()\nprint(a)\n"
            "a.insert(0, 9)\nprint(a[0])\n"
            "a.remove(1)\nprint(1 in a)\n"
        )
        self.assertEqual(out.split(), ["[2,", "1,", "3]", "9", "False"])

    def test_exception_types(self):
        out = run_capture(
            "try:\n"
            '    raise TypeError("bad type")\n'
            "except ValueError:\n"
            '    print("value")\n'
            "except TypeError:\n"
            '    print("type")\n'
        )
        self.assertIn("type", out)

    def test_finally_runs(self):
        out = run_capture(
            "try:\n"
            '    raise KeyError("k")\n'
            "except KeyError:\n"
            '    print("caught")\n'
            "finally:\n"
            '    print("done")\n'
        )
        self.assertEqual(out.split(), ["caught", "done"])

    def test_while_else(self):
        out = run_capture(
            "i = 0\n"
            "while i < 3:\n"
            "    print(i)\n"
            "    i += 1\n"
            "else:\n"
            '    print("done")\n'
        )
        self.assertEqual(out.split(), ["0", "1", "2", "done"])

    def test_big_number_literals(self):
        out = run_capture("print(10 ** 6)\nprint(0xDEADBEEF)\n")
        self.assertEqual(out.split(), ["1000000", "3735928559"])

    def test_global_in_class(self):
        out = run_capture(
            "counter = 0\n"
            "class Ticker:\n"
            "    def tick(self):\n"
            "        global counter\n"
            "        counter = counter + 1\n"
            "t = Ticker()\n"
            "t.tick()\n"
            "t.tick()\n"
            "print(counter)\n"
        )
        self.assertIn("2", out)

    def test_module_argv(self):
        out = run_capture(
            "import sys\n"
            "print(sys.argv[0])\n",
        )
        # no argv passed: argv is [<externum>]
        self.assertIn("<externum>", out)


if __name__ == "__main__":
    unittest.main()
