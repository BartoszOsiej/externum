"""Regression tests for Externum v3 additions (strict language).

Every program runs through the strict pipeline: bindings are declared with
types, parameters carry annotations, reassignment needs `mut`.
"""

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
            "data: List[Int] = [\n"
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
            "def f(x: Int) -> Int:\n    return x * 2\n"
            "data: List[Int] = [\n"
            "    f(1),\n"
            "    f(2),\n"
            "]\n"
            "print(data)\n"
        )
        self.assertIn("[2, 4]", out)

    def test_multiline_dict(self):
        out = run_capture(
            "d: Dict[Str, Int] = {\n"
            '    "a": 1,\n'
            '    "b": 2,\n'
            "}\n"
            'print(d["a"] + d["b"])\n'
        )
        self.assertIn("3", out)

    def test_multiline_call(self):
        out = run_capture(
            "def f(a: Int, b: Int, c: Int) -> Int:\n    return a + b + c\n"
            "print(f(\n"
            "    1,\n"
            "    2,\n"
            "    3,\n"
            "))\n"
        )
        self.assertIn("6", out)

    def test_multiline_nested(self):
        out = run_capture(
            "matrix: List[List[Int]] = [\n"
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
            "    def __init__(self, name: Str):\n"
            "        self.name = name\n"
            "\n"
            "    def hello(self) -> Str:\n"
            '        return "hi " + self.name\n'
            "\n"
            "    def bye(self) -> Str:\n"
            '        return "bye " + self.name\n'
            "\n"
            'g: Any = Greeter("Kot")\n'
            "print(g.hello())\n"
            "print(g.bye())\n"
        )
        self.assertEqual(out.split(), ["hi", "Kot", "bye", "Kot"])

    def test_inherited_method_call(self):
        out = run_capture(
            "class Base:\n"
            "    def greet(self) -> Str:\n"
            '        return "hello"\n'
            "\n"
            "class Child(Base):\n"
            "    def shout(self) -> Str:\n"
            "        return self.greet().upper()\n"
            "\n"
            "c: Any = Child()\n"
            "print(c.shout())\n"
        )
        self.assertIn("HELLO", out)


class TestTernaryAndUnpacking(unittest.TestCase):
    def test_ternary_expression(self):
        self.assertEqual(run_capture("print(1 if True else 2)\n"), "1\n")
        self.assertEqual(run_capture("print(1 if False else 2)\n"), "2\n")
        self.assertEqual(run_capture("print('a' if 3 > 2 else 'b')\n"), "a\n")

    def test_tuple_unpacking_swap(self):
        out = run_capture("mut a: Int = 1\nmut b: Int = 2\na, b = b, a\nprint(a, b)\n")
        self.assertIn("2 1", out)


class TestMoreFeatures(unittest.TestCase):
    def test_multiple_assignment_style(self):
        out = run_capture("mut a: Int = 1\nmut b: Int = 2\na, b = b, a\nprint(a + b)\n")
        self.assertIn("3", out)

    def test_nested_lambdas(self):
        out = run_capture(
            "add: Any = lambda a: lambda b: a + b\nprint(add(3)(4))\n"
        )
        self.assertIn("7", out)

    def test_dict_comprehension_like(self):
        out = run_capture(
            "names: List[Str] = [\"ala\", \"ola\"]\n"
            "caps: Dict[Str, Str] = {n: n.upper() for n in names}\n"
            'print(caps["ala"])\n'
        )
        self.assertIn("ALA", out)

    def test_chain_methods(self):
        out = run_capture(
            's: Str = "  a,b,c  "\n'
            'print(s.strip().replace("a", "x").split(","))\n'
        )
        self.assertIn("['x', 'b', 'c']", out)

    def test_string_multiply(self):
        out = run_capture('print("ab" * 3)\n')
        self.assertIn("ababab", out)

    def test_list_methods(self):
        out = run_capture(
            "a: List[Int] = [3, 1, 2]\n"
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
            "mut i: Int = 0\n"
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
            "counter: Int = 0\n"
            "class Ticker:\n"
            "    def tick(self) -> Void:\n"
            "        global counter\n"
            "        counter = counter + 1\n"
            "t: Any = Ticker()\n"
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

    # ---- regression: Compiler.compile() must return a dict for single targets
    # (bug: --target bash crashed with "list indices must be integers")

    def _compile(self, source: str, target: str):
        from externum.compiler import Compiler
        from externum.lexer import Lexer
        from externum.parser import Parser

        ast = list(Parser(Lexer(source).tokenize()).parse())
        return Compiler(ast).compile(target)

    def test_compile_single_targets_return_dict(self):
        src = 'x: Int = 1\nprint("hi")\n`echo inline`\n'
        for target in ("python", "bash", "binary"):
            result = self._compile(src, target)
            self.assertIsInstance(result, dict, f"target {target!r} must return dict")
            self.assertIn(target, result)
            self.assertIsInstance(result[target], str)

    def test_compile_all_returns_all_targets(self):
        src = 'x: Int = 1\nprint("hi")\n`echo inline`\n'
        result = self._compile(src, "all")
        self.assertEqual(set(result.keys()), {"python", "bash", "binary"})
        self.assertIn("import subprocess", result["python"])

    def test_compile_unknown_target_raises(self):
        with self.assertRaises(ValueError):
            self._compile('x: Int = 1\n', "wasm")

    def test_compile_bash_target_runs(self):
        # end-to-end: emitted bash for a bash-only program must be non-empty
        result = self._compile('`echo hello-from-bash`\n', "bash")
        self.assertIn("echo hello-from-bash", result["bash"])

    # ---- EXBC artifacts: compile --target bytecode -> save -> load -> run

    def test_exbc_artifact_roundtrip_runs(self):
        import contextlib
        import io
        import tempfile

        from externum.bytecode import BytecodeCompiler, load_module, module_to_bytes, save_module
        from externum.vm import VM

        source = 'x: Int = 0b1010\ny: Int = 42\nprint($"sum={x+y}")\n'
        ast = list(Parser(Lexer(source).tokenize()).parse())
        module = BytecodeCompiler(ast, module_name="artifact.ext").compile()

        with tempfile.NamedTemporaryFile(suffix=".exbc", delete=False) as fh:
            path = fh.name
        try:
            save_module(module, path)
            with open(path, "rb") as fh:
                blob = fh.read()
            self.assertTrue(blob.startswith(b"EXBC"))
            loaded = load_module(path)
            self.assertEqual(module_to_bytes(loaded), blob)  # stable roundtrip

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                VM().run_module(loaded)
            self.assertIn("sum=52", out.getvalue())
        finally:
            os.unlink(path)

    def test_exbc_artifact_rejects_garbage(self):
        from externum.bytecode import module_from_bytes

        with self.assertRaises(ValueError):
            module_from_bytes(b"NOPE" + b"\x00" * 30)
        with self.assertRaises(ValueError):
            module_from_bytes(b"EXBC" + (99).to_bytes(2, "big") + b"\x00" * 20)

    def _run_vm(self, src: str) -> str:
        from externum.bytecode import BytecodeCompiler
        from externum.lexer import Lexer
        from externum.parser import Parser
        from externum.vm import VM

        ast = Parser(Lexer(src).tokenize()).parse()
        module = BytecodeCompiler(ast).compile()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            VM().run_module(module)
        return out.getvalue()

    def test_vm_aug_assign_module_level(self):
        # Issue #21: at module top level, AUG_ASSIGN stored to a local frame
        # nothing ever reads — loop counters never advanced (silent hang).
        self.assertEqual(
            self._run_vm("mut i: Int = 0\nwhile i < 3:\n    i += 1\nprint(i)\n").strip(),
            "3",
        )

    def test_vm_aug_assign_operator_semantics(self):
        # Issue #21 (related): the parser reports "*=", the op_map had "*" —
        # every augmented op except += silently degraded to addition.
        self.assertEqual(self._run_vm("mut x: Int = 3\nx *= 4\nprint(x)\n").strip(), "12")
        self.assertEqual(self._run_vm("mut x: Int = 10\nx -= 4\nprint(x)\n").strip(), "6")
        self.assertEqual(self._run_vm("mut x: Int = 13\nx %= 5\nprint(x)\n").strip(), "3")

    def test_vm_aug_assign_in_function(self):
        src = (
            "def count(n: Int) -> Int:\n"
            "    mut acc: Int = 0\n"
            "    mut k: Int = 0\n"
            "    while k < n:\n"
            "        acc += k\n"
            "        k += 1\n"
            "    return acc\n"
            "print(count(5))\n"
        )
        self.assertEqual(self._run_vm(src).strip(), "10")

    def test_vm_parenthesized_rhs(self):
        # Issue #22: parenthesized RHS text fell through to _compile_name
        # ("undefined global (((...)))").
        src = (
            "mut total: Int = 0\n"
            "mut i: Int = 0\n"
            "while i < 5:\n"
            "    total = total + ((i * 3 + 7) % 1000)\n"
            "    i = i + 1\n"
            "print(total)\n"
        )
        self.assertEqual(self._run_vm(src).strip(), "65")
        # same but with the augmented form
        src2 = (
            "mut total: Int = 0\n"
            "mut i: Int = 0\n"
            "while i < 5:\n"
            "    total += ((i * 3 + 7) % 1000)\n"
            "    i += 1\n"
            "print(total)\n"
        )
        self.assertEqual(self._run_vm(src2).strip(), "65")

    def _compile_py(self, src: str) -> str:
        from externum.compiler import Compiler
        from externum.lexer import Lexer
        from externum.parser import Parser

        return Compiler(list(Parser(Lexer(src).tokenize()).parse())).compile("python")["python"]

    def test_pipe_operator_python_target(self):
        # v4.2: `x |> f(a, b)` desugars to `f(x, a, b)` in the transpiler.
        src = (
            "def double2(n: Int, m: Int) -> Int:\n"
            "    return n * m\n"
            "mut r: Int = 5 |> double2(3)\n"
            "print(r)\n"
        )
        self.assertIn("double2(5, 3)", self._compile_py(src))

    def test_pipe_operator_vm(self):
        src = (
            "def double2(n: Int, m: Int) -> Int:\n"
            "    return n * m\n"
            "mut r: Int = 5 |> double2(3)\n"
            "print(r)\n"
        )
        self.assertEqual(self._run_vm(src).strip(), "15")

    def test_fn_alias(self):
        # v4.2: `fn` is accepted as an alias for `def`.
        src = (
            "fn triple(n: Int) -> Int:\n"
            "    return n * 3\n"
            "print(4 |> triple())\n"
        )
        self.assertEqual(self._run_vm(src).strip(), "12")
        self.assertIn("triple(4)", self._compile_py(src))

    def test_bash_backend_loop(self):
        # v4.2: the bash target translates real Externum logic instead of
        # emitting an empty script (#19 follow-up).
        from externum.bash_backend import BashCodegen
        from externum.lexer import Lexer
        from externum.parser import Parser

        ast = list(Parser(Lexer("mut i: Int = 0\nwhile i < 3:\n    i += 1\nprint(i)\n").tokenize()).parse())
        code, warnings = BashCodegen(ast).generate()
        self.assertIn("while", code)
        self.assertIn("i=$(( i + 1 ))", code)
        self.assertIn("echo ${i}", code)
        self.assertEqual(warnings, [])

        # unsupported statements produce warnings, never silent emptiness
        ast2 = list(Parser(Lexer("def f(n: Int) -> Int:\n    return n\nprint(f(1))\n").tokenize()).parse())
        code2, warnings2 = BashCodegen(ast2).generate()
        self.assertTrue(any("not supported" in w for w in warnings2))


if __name__ == "__main__":
    unittest.main()
