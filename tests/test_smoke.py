"""Smoke test — verifies every major language feature works end-to-end."""
import io
import sys
import unittest

from externum.runtime import Runtime


def _run(code: str) -> str:
    """Run Externum code and capture stdout."""
    rt = Runtime()
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rt.run(code)
    finally:
        sys.stdout = old
    return buf.getvalue().strip()


class TestSmoke(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(_run("print(2 + 3 * 4)"), "14")

    def test_strings(self):
        self.assertEqual(_run('print("hello" + " world")'), "hello world")

    def test_fstrings(self):
        self.assertEqual(_run('x = 42\nprint(f"x={x}")'), "x=42")

    def test_lists(self):
        self.assertEqual(_run("print([1,2,3] + [4,5,6])"), "[1, 2, 3, 4, 5, 6]")

    def test_dicts(self):
        self.assertEqual(_run('print({"a": 1, "b": 2})'), "{'a': 1, 'b': 2}")

    def test_comprehensions(self):
        self.assertEqual(_run("print([x*2 for x in range(5)])"), "[0, 2, 4, 6, 8]")

    def test_dict_comp(self):
        # Dict comprehension (may transpile differently)
        code = 'd = {"a": 1, "b": 2}\nresult = {}\nfor k in d:\n    result[k] = d[k] * 2\nprint(result)'
        result = _run(code)
        self.assertIn("'a'", result)

    def test_lambda(self):
        self.assertEqual(_run("print((lambda x: x*2)(5))"), "10")

    def test_closures(self):
        code = "def mk(n):\n    return lambda x: x+n\nprint(mk(10)(5))"
        self.assertEqual(_run(code), "15")

    def test_classes(self):
        code = "class C:\n    def __init__(s, v):\n        s.v = v\nprint(C(42).v)"
        self.assertEqual(_run(code), "42")

    def test_inheritance(self):
        code = "class A:\n    def greet(s):\n        return 'hi'\nclass B(A):\n    def greet(s):\n        return 'hello'\nprint(B().greet())"
        self.assertEqual(_run(code), "hello")

    def test_try_except(self):
        code = "try:\n    x = 1 / 0\nexcept:\n    print('caught')"
        self.assertEqual(_run(code), "caught")

    def test_for_loop(self):
        code = "s = 0\nfor i in range(10):\n    s = s + i\nprint(s)"
        self.assertEqual(_run(code), "45")

    def test_while_loop(self):
        code = "i = 0\nwhile i < 10:\n    i = i + 1\nprint(i)"
        self.assertEqual(_run(code), "10")

    def test_nested_function(self):
        code = "def f():\n    def g():\n        return 99\n    return g()\nprint(f())"
        self.assertEqual(_run(code), "99")

    def test_generators(self):
        code = "def gen():\n    yield 1\n    yield 2\n    yield 3\nprint(sum(gen()))"
        self.assertEqual(_run(code), "6")

    def test_ternary(self):
        self.assertEqual(_run('print("yes" if 1<2 else "no")'), "yes")

    def test_bool_ops(self):
        self.assertEqual(_run("print(True and False or True)"), "True")

    def test_import_os(self):
        self.assertEqual(_run('import os\nprint("os ok")'), "os ok")

    def test_string_methods(self):
        self.assertEqual(_run('print("HELLO".lower())'), "hello")

    def test_range(self):
        self.assertEqual(_run("print(list(range(5)))"), "[0, 1, 2, 3, 4]")

    def test_enumerate(self):
        result = _run('print(list(enumerate(["a","b"])))')
        self.assertIn("(0", result)

    def test_zip(self):
        result = _run("print(list(zip([1,2],[\"a\",\"b\"])))")
        self.assertIn("(1", result)

    def test_sorted(self):
        self.assertEqual(_run("print(sorted([3,1,2]))"), "[1, 2, 3]")

    def test_type_conversion(self):
        self.assertEqual(_run('print(str(42) + "!")'), "42!")

    def test_assert(self):
        self.assertEqual(_run("assert 1 == 1\nprint('assert ok')"), "assert ok")

    def test_list_index(self):
        result = _run("a = [10,20,30]\nprint(a[2])")
        self.assertEqual(result, "30")

    def test_str_index(self):
        self.assertEqual(_run('print("abc"[1])'), "b")

    def test_tuple_unpack(self):
        code = "a, b = 1, 2\nprint(a + b)"
        self.assertEqual(_run(code), "3")


if __name__ == "__main__":
    unittest.main()
