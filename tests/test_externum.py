"""Comprehensive conformance tests for Externum v3.

Run with:  python3 -m unittest discover -s tests -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum import Lexer, Parser, Compiler, Runtime  # noqa: E402


def compile_all(source):
    tokens = Lexer(source).tokenize()
    ast = list(Parser(tokens).parse())
    return Compiler(ast).compile("all")


def run_capture(source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        Runtime().run(source)
    return out.getvalue()


def py_of(source):
    return compile_all(source)["python"]


# =================================================================== LEXER
class TestLexer(unittest.TestCase):
    def test_binary_number(self):
        toks = Lexer("mask = 0b1010\n").tokenize()
        self.assertEqual([t.value for t in toks if t.type == "BINARY_NUMBER"], [0b1010])

    def test_hex_number(self):
        toks = Lexer("h = 0xFF\n").tokenize()
        self.assertEqual([t.value for t in toks if t.type == "NUMBER"], [255])

    def test_keywords(self):
        src = "class try except finally raise import from as lambda with assert del yield global nonlocal"
        types = {t.type for t in Lexer(src + "\n").tokenize()}
        for k in ("CLASS", "TRY", "EXCEPT", "FINALLY", "RAISE", "IMPORT",
                  "FROM", "AS", "LAMBDA", "WITH", "ASSERT", "DEL", "YIELD",
                  "GLOBAL", "NONLOCAL"):
            self.assertIn(k, types)

    def test_self_literal_tokens(self):
        types = {t.type for t in Lexer("self = 1\n").tokenize()}
        self.assertIn("SELF", types)
        types = {t.type for t in Lexer("x = True\n").tokenize()}
        self.assertIn("TRUE", types)

    def test_bitwise_operators(self):
        types = {t.type for t in Lexer("a & b | c ^ d ~e << f >> g\n").tokenize()}
        for op in ("&", "|", "^", "~", "<<", ">>"):
            self.assertIn(op, types)

    def test_floor_division(self):
        toks = Lexer("a // b\n").tokenize()
        self.assertIn("//", {t.type for t in toks})

    def test_triple_string(self):
        toks = Lexer('s = """hello\nworld"""\n').tokenize()
        strings = [t.value for t in toks if t.type == "STRING"]
        self.assertTrue(any('"""' in s for s in strings))

    def test_inline_bash(self):
        toks = Lexer("`ls -la`\n").tokenize()
        self.assertTrue(any(t.type == "BASH_START" for t in toks))

    def test_bash_block(self):
        toks = Lexer("%%\necho hi\n%%\n").tokenize()
        self.assertTrue(any(t.type == "BASH_BLOCK" for t in toks))

    def test_fstring(self):
        toks = Lexer('print(f"x={1}")\n').tokenize()
        strings = [t.value for t in toks if t.type == "STRING"]
        self.assertTrue(any(v.startswith('f"') for v in strings))


# =================================================================== PARSER
class TestParser(unittest.TestCase):
    def parse(self, source):
        return list(Parser(Lexer(source).tokenize()).parse())

    def test_list_literal(self):
        ast = self.parse("x = [1, 2, 3]\n")
        self.assertEqual(ast[0].type, "ASSIGN")
        self.assertEqual(ast[0].children[1].value, "[1, 2, 3]")

    def test_empty_list(self):
        ast = self.parse("x = []\n")
        self.assertEqual(ast[0].children[1].value, "[]")

    def test_dict_literal(self):
        ast = self.parse('x = {"a": 1, "b": 2}\n')
        self.assertEqual(ast[0].children[1].value, '{"a": 1, "b": 2}')

    def test_empty_dict(self):
        ast = self.parse("x = {}\n")
        self.assertEqual(ast[0].children[1].value, "{}")

    def test_set_literal(self):
        ast = self.parse("x = {1, 2, 3}\n")
        self.assertEqual(ast[0].children[1].value, "{1, 2, 3}")

    def test_tuple_literal(self):
        ast = self.parse("x = (1, 2)\n")
        self.assertEqual(ast[0].children[1].value, "(1, 2)")

    def test_indexing(self):
        ast = self.parse("y = x[0]\n")
        self.assertEqual(ast[0].children[1].value, "x[0]")

    def test_slicing(self):
        for src, want in [
            ("y = x[1:3]\n", "x[1:3]"),
            ("y = x[:3]\n", "x[:3]"),
            ("y = x[1:]\n", "x[1:]"),
            ("y = x[::2]\n", "x[::2]"),
            ("y = x[:]\n", "x[:]"),
            ("y = x[1:5:2]\n", "x[1:5:2]"),
        ]:
            ast = self.parse(src)
            self.assertEqual(ast[0].children[1].value, want, src)

    def test_member_access(self):
        ast = self.parse("y = obj.attr\n")
        self.assertEqual(ast[0].children[1].value, "obj.attr")

    def test_method_call(self):
        ast = self.parse("y = items.append(1)\n")
        call = ast[0].children[1]
        self.assertEqual(call.type, "CALL")
        self.assertEqual(call.value, "items.append")
        self.assertEqual(len(call.children), 1)

    def test_index_assignment(self):
        ast = self.parse("x[0] = 5\n")
        self.assertEqual(ast[0].type, "ASSIGN")
        self.assertEqual(ast[0].children[0].value, "x[0]")

    def test_keyword_args(self):
        ast = self.parse("f(a=1, b=2)\n")
        call = ast[0]
        kinds = [c.type for c in call.children]
        self.assertIn("KWARG", kinds)

    def test_class_def(self):
        ast = self.parse("class Animal:\n    pass\n")
        self.assertEqual(ast[0].type, "CLASS")
        self.assertEqual(ast[0].value, "Animal")

    def test_class_inheritance(self):
        ast = self.parse("class Cat(Animal):\n    pass\n")
        self.assertEqual(ast[0].children[0].value, "Animal")

    def test_try_except(self):
        ast = self.parse("try:\n    x = 1\nexcept ValueError as e:\n    x = 2\n")
        kinds = [c.type for c in ast[0].children]
        self.assertIn("EXCEPT", kinds)

    def test_try_else_finally(self):
        ast = self.parse("try:\n    x = 1\nexcept:\n    x = 2\nelse:\n    x = 3\nfinally:\n    x = 4\n")
        kinds = [c.type for c in ast[0].children]
        self.assertIn("TRY_ELSE", kinds)
        self.assertIn("FINALLY", kinds)

    def test_import(self):
        ast = self.parse("import os.path\n")
        self.assertEqual(ast[0].value, "import os.path")
        ast = self.parse("from os import path\n")
        self.assertEqual(ast[0].value, "from os import path")
        ast = self.parse("from . import x\n")
        self.assertEqual(ast[0].value, "from . import x")

    def test_lambda(self):
        ast = self.parse("f = lambda x, y: x + y\n")
        lam = ast[0].children[1]
        self.assertEqual(lam.type, "LAMBDA")
        self.assertEqual(lam.value, "x, y")
        self.assertIn("lambda x, y: x + y", py_of("f = lambda x, y: x + y\n"))

    def test_ternary(self):
        ast = self.parse("y = 1 if x > 5 else 2\n")
        self.assertEqual(ast[0].children[1].value, "1 if x > 5 else 2")

    def test_comprehension(self):
        ast = self.parse("y = [i * 2 for i in range(10) if i % 2 == 0]\n")
        self.assertEqual(
            ast[0].children[1].value,
            "[i * 2 for i in range(10) if i % 2 == 0]",
        )

    def test_unary_minus(self):
        ast = self.parse("y = -x\n")
        self.assertEqual(ast[0].children[1].value, "-x")

    def test_bitwise(self):
        ast = self.parse("y = a & b | c ^ d\n")
        self.assertEqual(ast[0].children[1].value, "a & b | c ^ d")

    def test_precedence(self):
        ast = self.parse("y = 1 + 2 * 3\n")
        self.assertEqual(ast[0].children[1].value, "1 + 2 * 3")

    def test_default_params(self):
        ast = self.parse("def f(a, b=2):\n    return a + b\n")
        self.assertEqual(ast[0].children[0].value, "a, b=2")

    def test_star_params(self):
        ast = self.parse("def f(*args, **kwargs):\n    pass\n")
        self.assertEqual(ast[0].children[0].value, "*args, **kwargs")

    def test_with_stmt(self):
        ast = self.parse("with open('f') as fh:\n    x = fh.read()\n")
        self.assertEqual(ast[0].type, "WITH")

    def test_assert_stmt(self):
        ast = self.parse("assert x > 0\n")
        self.assertEqual(ast[0].type, "ASSERT")

    def test_del_stmt(self):
        ast = self.parse("del x[0]\n")
        self.assertEqual(ast[0].type, "DEL")


# ================================================================= COMPILER
class TestCompiler(unittest.TestCase):
    def test_class_python(self):
        code = py_of("class A:\n    def f(self):\n        return 1\n")
        self.assertIn("class A:", code)
        self.assertIn("def f(self):", code)

    def test_class_bases(self):
        code = py_of("class B(A, C):\n    pass\n")
        self.assertIn("class B(A, C):", code)

    def test_try_except_python(self):
        code = py_of("try:\n    x = 1\nexcept ValueError as e:\n    x = 2\n")
        self.assertIn("try:", code)
        self.assertIn("except ValueError as e:", code)

    def test_import_passthrough(self):
        code = py_of("import os\nfrom os import path as p\n")
        self.assertIn("import os", code)
        self.assertIn("from os import path as p", code)

    def test_bash_block_adds_subprocess(self):
        result = compile_all("%%\necho hi\n%%\n")
        self.assertIn("import subprocess", result["python"])
        self.assertIn("echo hi", result["bash"])

    def test_elif_compiles(self):
        code = py_of("if x > 5:\n    a = 1\nelif x > 0:\n    a = 2\nelse:\n    a = 3\n")
        self.assertIn("if x > 5:", code)
        self.assertIn("elif x > 0:", code)
        self.assertIn("else:", code)


# ================================================================= RUNTIME
class TestRuntime(unittest.TestCase):
    def test_hello(self):
        out = run_capture('print("Hello from Externum!")\n')
        self.assertIn("Hello from Externum!", out)

    def test_binary_arithmetic(self):
        out = run_capture("x = 0b1010\ny = 42\nprint(x + y)\n")
        self.assertIn("52", out)

    def test_while_loop(self):
        out = run_capture("i = 0\nwhile i < 3:\n    print(i)\n    i += 1\n")
        self.assertEqual(out.split(), ["0", "1", "2"])

    def test_for_loop(self):
        out = run_capture("for i in range(3):\n    print(i)\n")
        self.assertEqual(out.split(), ["0", "1", "2"])

    def test_if_elif_else(self):
        out = run_capture('x = 10\nif x > 5:\n    print("large")\nelif x > 0:\n    print("small")\nelse:\n    print("none")\n')
        self.assertIn("large", out)

    def test_recursion(self):
        out = run_capture("def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(5))\n")
        self.assertIn("120", out)

    def test_fstring(self):
        out = run_capture('x = 42\nprint(f"value: {x}")\n')
        self.assertIn("value: 42", out)

    def test_lists(self):
        out = run_capture("a = [1, 2, 3]\na.append(4)\nprint(a[0])\nprint(a[-1])\nprint(len(a))\n")
        self.assertEqual(out.split(), ["1", "4", "4"])

    def test_slicing(self):
        out = run_capture("a = [0, 1, 2, 3, 4]\nprint(a[1:3])\nprint(a[::-1])\nprint(a[::2])\n")
        self.assertIn("[1, 2]", out)
        self.assertIn("[4, 3, 2, 1, 0]", out)
        self.assertIn("[0, 2, 4]", out)

    def test_dicts(self):
        out = run_capture('d = {"a": 1, "b": 2}\nd["c"] = 3\nprint(d["a"] + d["c"])\nprint(len(d))\n')
        self.assertEqual(out.split(), ["4", "3"])

    def test_strings(self):
        out = run_capture('s = "Externum"\nprint(s.upper())\nprint(s[0])\nprint(s[::-1])\n')
        self.assertIn("EXTERNUM", out)
        self.assertIn("E", out)
        self.assertIn("munretxE", out)

    def test_class_basics(self):
        out = run_capture(
            'class Animal:\n    def __init__(self, name):\n        self.name = name\n'
            '    def speak(self):\n        print("... from " + self.name)\n'
            'a = Animal("Rex")\na.speak()\n'
        )
        self.assertIn("... from Rex", out)

    def test_class_inheritance(self):
        out = run_capture(
            'class Animal:\n    def __init__(self, name):\n        self.name = name\n'
            '    def speak(self):\n        print("generic")\n'
            'class Dog(Animal):\n    def speak(self):\n        print("woof " + self.name)\n'
            'd = Dog("Burek")\nd.speak()\n'
        )
        self.assertIn("woof Burek", out)

    def test_exceptions(self):
        out = run_capture(
            "try:\n    x = 1 / 0\nexcept ZeroDivisionError as e:\n    print(\"caught\")\n"
        )
        self.assertIn("caught", out)

    def test_raise(self):
        out = run_capture(
            'def f():\n    raise ValueError("boom")\n'
            "try:\n    f()\nexcept ValueError as e:\n    print(e)\n"
        )
        self.assertIn("boom", out)

    def test_try_else_finally(self):
        out = run_capture(
            "try:\n    x = 1\nexcept:\n    print(\"no\")\nelse:\n    print(\"yes\")\nfinally:\n    print(\"fin\")\n"
        )
        self.assertEqual(out.split(), ["yes", "fin"])

    def test_lambda(self):
        out = run_capture("f = lambda x, y: x * y\nprint(f(3, 4))\n")
        self.assertIn("12", out)

    def test_ternary(self):
        out = run_capture("x = 10\nprint(\"big\" if x > 5 else \"small\")\n")
        self.assertIn("big", out)

    def test_comprehension(self):
        out = run_capture("squares = [i * i for i in range(5)]\nprint(squares)\n")
        self.assertIn("[0, 1, 4, 9, 16]", out)

    def test_comprehension_filter(self):
        out = run_capture("evens = [i for i in range(10) if i % 2 == 0]\nprint(evens)\n")
        self.assertIn("[0, 2, 4, 6, 8]", out)

    def test_default_args(self):
        out = run_capture("def f(a, b=10):\n    return a + b\nprint(f(1))\nprint(f(1, 2))\n")
        self.assertEqual(out.split(), ["11", "3"])

    def test_kwargs_call(self):
        out = run_capture("def f(a, b):\n    return a - b\nprint(f(b=1, a=5))\n")
        self.assertIn("4", out)

    def test_star_args(self):
        out = run_capture("def f(*args):\n    return len(args)\nprint(f(1, 2, 3))\n")
        self.assertIn("3", out)

    def test_generators(self):
        out = run_capture(
            "def gen():\n    yield 1\n    yield 2\n    yield 3\n"
            "for v in gen():\n    print(v)\n"
        )
        self.assertEqual(out.split(), ["1", "2", "3"])

    def test_import_lib_strings(self):
        out = run_capture(
            "import strings\nprint(strings.reverse(\"abc\"))\nprint(strings.is_palindrome(\"kajak\"))\n"
        )
        self.assertEqual(out.split(), ["cba", "True"])

    def test_import_lib_mathx(self):
        out = run_capture(
            "import mathx\nprint(mathx.factorial(5))\nprint(mathx.is_even(7))\nprint(mathx.gcd(12, 8))\n"
        )
        self.assertEqual(out.split(), ["120", "False", "4"])

    def test_import_lib_collections(self):
        out = run_capture(
            "import structs\ns = structs.Stack()\ns.push(1)\ns.push(2)\nprint(s.pop())\nprint(s.size())\n"
        )
        self.assertEqual(out.split(), ["2", "1"])

    def test_assert_passes(self):
        out = run_capture("x = 5\nassert x > 0\nprint(\"ok\")\n")
        self.assertIn("ok", out)

    def test_assert_fails(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                Runtime().run("x = 5\nassert x < 0\n")
            except AssertionError:
                out.write("asserted")
        self.assertIn("asserted", out.getvalue())

    def test_with_statement(self):
        out = run_capture(
            'with open("/tmp/ext_test_file.txt", "w") as f:\n    f.write("hi")\n'
            'f2 = open("/tmp/ext_test_file.txt", "r")\nprint(f2.read())\nf2.close()\n'
        )
        self.assertIn("hi", out)

    def test_bitwise_runtime(self):
        out = run_capture("print(0b1100 & 0b1010)\nprint(1 << 4)\nprint(5 | 2)\nprint(~0)\n")
        self.assertEqual(out.split(), ["8", "16", "7", "-1"])

    def test_unary_minus_runtime(self):
        out = run_capture("x = 5\nprint(-x)\nprint(2 ** 3)\n")
        self.assertEqual(out.split(), ["-5", "8"])

    def test_nested_structures(self):
        out = run_capture(
            "matrix = [[1, 2], [3, 4]]\nprint(matrix[1][0])\n"
            'people = [{"name": "Ala", "age": 3}, {"name": "Ola", "age": 5}]\nprint(people[1]["name"])\n'
        )
        self.assertEqual(out.split(), ["3", "Ola"])

    def test_bash_inline_compiles(self):
        result = compile_all("`echo from-bash`\n")
        self.assertIn('subprocess.run("echo from-bash", shell=True)', result["python"])

    def test_bash_block_runs(self):
        result = compile_all("%%\necho hi\n%%\n")
        self.assertIn("echo hi", result["bash"])

    def test_increments(self):
        out = run_capture("x = 10\nx += 5\nx *= 2\nprint(x)\n")
        self.assertIn("30", out)

    def test_boolean_logic(self):
        out = run_capture('print(True and False)\nprint(True or False)\nprint(not True)\n')
        self.assertEqual(out.split(), ["False", "True", "False"])

    def test_comparison_chain(self):
        out = run_capture("x = 5\nprint(0 < x < 10)\nprint(x == 5)\nprint(x != 3)\n")
        self.assertEqual(out.split(), ["True", "True", "True"])

    def test_math_ops(self):
        out = run_capture("print(7 // 2)\nprint(7 % 2)\nprint(2 ** 8)\nprint(abs(-3))\n")
        self.assertEqual(out.split(), ["3", "1", "256", "3"])

    def test_string_methods(self):
        out = run_capture('s = "  Hello World  "\nprint(s.strip().lower())\nprint("a,b,c".split(","))\n')
        self.assertIn("hello world", out)
        self.assertIn("['a', 'b', 'c']", out)

    def test_sorting(self):
        out = run_capture("nums = [3, 1, 2]\nnums.sort()\nprint(nums)\nprint(sorted(nums, reverse=True))\n")
        self.assertIn("[1, 2, 3]", out)
        self.assertIn("[3, 2, 1]", out)

    def test_enumerate_zip(self):
        out = run_capture("for i, v in enumerate([\"a\", \"b\"]):\n    print(i, v)\n")
        self.assertIn("0 a", out)
        self.assertIn("1 b", out)

    def test_global_stmt(self):
        out = run_capture(
            "counter = 0\n"
            "def bump():\n    global counter\n    counter = counter + 1\n"
            "bump()\nbump()\nprint(counter)\n"
        )
        self.assertIn("2", out)

    def test_closures(self):
        out = run_capture(
            "def make_adder(n):\n    def adder(x):\n        return x + n\n    return adder\n"
            "add5 = make_adder(5)\nprint(add5(10))\n"
        )
        self.assertIn("15", out)

    def test_argv(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            Runtime().run("import sys\nprint(len(sys.argv))\n", argv=["a", "b"])
        self.assertIn("3", out.getvalue())  # [script, a, b]

    def test_runtime_file(self):
        with open("/tmp/ext_rt_file.ext", "w") as fh:
            fh.write('print("from file")\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            Runtime().run_file("/tmp/ext_rt_file.ext")
        self.assertIn("from file", out.getvalue())

    def test_repl_completeness(self):
        rt = Runtime()
        self.assertFalse(rt._is_complete(["if True:"]))
        self.assertFalse(rt._is_complete(["if True:", "    print(1)"]))
        self.assertTrue(rt._is_complete(["if True:", "    print(1)", ""]))
        self.assertTrue(rt._is_complete(["x = 1"]))

    def test_hex_literal_runtime(self):
        out = run_capture("print(0xFF)\nprint(0x10 + 2)\n")
        self.assertEqual(out.split(), ["255", "18"])

    def test_triple_string_runtime(self):
        out = run_capture('s = """line1\nline2"""\nprint(len(s))\n')
        self.assertIn("11", out)

    def test_deep_expression(self):
        out = run_capture("print((1 + 2) * (3 + 4))\nprint(2 * 3 + 4 * 5)\n")
        self.assertEqual(out.split(), ["21", "26"])

    def test_class_counter_usage(self):
        out = run_capture(
            "import structs\nc = structs.Counter([1, 2, 2, 3, 3, 3])\n"
            "print(c.get(3))\nprint(c.total())\nprint(c.most_common()[0])\n"
        )
        self.assertIn("3", out)
        self.assertIn("6", out)
        self.assertIn("(3, 3)", out)

    def test_slugify(self):
        out = run_capture('import strings\nprint(strings.slugify("Hello World!"))\n')
        self.assertIn("hello-world", out)

    def test_star_args_sum(self):
        out = run_capture(
            "def total(*nums):\n    s = 0\n    for n in nums:\n        s = s + n\n    return s\nprint(total(1, 2, 3, 4))\n"
        )
        self.assertIn("10", out)

    def test_nested_functions(self):
        out = run_capture(
            "def outer():\n    def inner():\n        return 42\n    return inner()\nprint(outer())\n"
        )
        self.assertIn("42", out)

    def test_while_break_continue(self):
        out = run_capture(
            "i = 0\nwhile True:\n    i = i + 1\n    if i == 2:\n        continue\n    if i > 4:\n        break\n    print(i)\n"
        )
        self.assertEqual(out.split(), ["1", "3", "4"])


if __name__ == "__main__":
    unittest.main()
