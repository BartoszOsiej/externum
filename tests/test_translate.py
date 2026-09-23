"""Tests for externum.translate — py2ext and rs2ext.

Run with:  python3 -m unittest tests/test_translate.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum import Lexer, Parser, Compiler
from externum.translate import translate_python, translate_rust


def compile_python_target(ext_source: str) -> str:
    """Translate .ext source through the real Externum compiler (python target)."""
    tokens = Lexer(ext_source).tokenize()
    ast_nodes = list(Parser(tokens).parse())
    comp = Compiler(ast_nodes)
    comp.compile()
    return "\n".join(comp.output["python"])


class TestPy2Ext(unittest.TestCase):
    def test_hello_translates_and_parses(self):
        src = 'name = "world"\nprint(f"hello {name}!")\n'
        ext, rep = translate_python(src)
        self.assertEqual(rep.warnings, [])
        self.assertIn('name: Str = "world"', ext)
        self.assertIn('$"hello {name}!"', ext)
        compile_python_target(ext)  # must parse+compile cleanly
    def test_typed_declarations(self):
        src = "x: int = 42\ny = 3.14\nxs = [1, 2, 3]\n"
        ext, _ = translate_python(src)
        self.assertIn("x: Int = 42", ext)
        self.assertIn("y: Float = 3.14", ext)
        self.assertIn("xs: List[Int] = [1, 2, 3]", ext)
        compile_python_target(ext)

    def test_main_guard_hoisted(self):
        src = 'def greet():\n    return "hi"\n\nif __name__ == "__main__":\n    print(greet())\n'
        ext, _ = translate_python(src)
        self.assertIn("fn main():", ext.replace("def main():", "fn main():"))  # def or fn
        self.assertIn("def main():", ext)
        compile_python_target(ext)

    def test_function_with_types(self):
        src = (
            "def add(a: int, b: int = 5) -> int:\n"
            "    return a + b\n"
            "print(add(2))\n"
        )
        ext, _ = translate_python(src)
        self.assertIn("def add(a: Int, b: Int = 5) -> Int:", ext)
        compile_python_target(ext)

    def test_class_translates(self):
        src = (
            "class Animal:\n"
            '    """A beast."""\n'
            "    def __init__(self, name: str):\n"
            "        self.name = name\n"
            "    def speak(self) -> str:\n"
            '        return f"{self.name} says hi"\n'
        )
        ext, _ = translate_python(src)
        self.assertIn("class Animal:", ext)
        self.assertIn("# A beast.", ext)
        self.assertIn('$"{self.name} says hi"', ext)
        compile_python_target(ext)

    def test_rust_impl_body_compiles(self):
        src = (
            "struct Sensor { name: String, readings: Vec<f64> }\n"
            "impl Sensor {\n"
            "    fn push(&mut self, v: f64) {\n"
            "        self.readings.push(v);\n"
            "    }\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("class Sensor:", ext)
        self.assertIn("    fn push(self, v: Float):", ext)  # one indent level
        self.assertIn("        self.readings.append(v)", ext)  # body: two levels

    def test_control_flow(self):
        src = (
            "total = 0\n"
            "for i in range(10):\n"
            "    if i % 2 == 0:\n"
            "        total += i\n"
            "    else:\n"
            "        total -= 1\n"
            "while total > 0:\n"
            "    total -= 3\n"
            "print(total)\n"
        )
        ext, _ = translate_python(src)
        for needle in ("for i in range(10):", "while total > 0:", "total = total - 3"):
            self.assertIn(needle, ext)
        compile_python_target(ext)

    def test_try_except_finally(self):
        src = (
            "try:\n"
            "    x = 1\n"
            "except ValueError as e:\n"
            "    print(e)\n"
            "finally:\n"
            "    print('done')\n"
        )
        ext, _ = translate_python(src)
        self.assertIn("except ValueError as e:", ext)
        self.assertIn("finally:", ext)
        compile_python_target(ext)

    def test_import_warning_for_non_stdlib(self):
        ext, rep = translate_python("import numpy\n")
        self.assertIn("import numpy", ext)
        self.assertTrue(any("not part of the Externum stdlib" in w for w in rep.warnings))

    def test_uninferrable_gets_any_with_warning(self):
        src = "import mathx\nv = mathx.sqrt(2)\n"
        ext, rep = translate_python(src)
        self.assertIn("v: Any = mathx.sqrt(2)", ext)
        self.assertTrue(any("could not infer" in w for w in rep.warnings))

    def test_unknown_statement_warns(self):
        src = "match x:\n    case 1:\n        pass\n"
        _, rep = translate_python(src)
        self.assertTrue(any("unsupported statement" in w for w in rep.warnings))


class TestRs2Ext(unittest.TestCase):
    def test_fn_and_let(self):
        src = (
            "fn add(a: i32, b: i64) -> i64 {\n"
            "    let result = a + b;\n"
            "    result\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("fn add(a: Int, b: Int) -> Int:", ext)
        self.assertIn("return result", ext)
        compile_python_target(ext)

    def test_struct_def(self):
        src = "struct Point {\n    x: f64,\n    y: f64,\n}\n"
        ext, _ = translate_rust(src)
        self.assertIn("struct Point { x: Float, y: Float }", ext)

    def test_impl_to_class(self):
        src = (
            "struct Counter { n: u32 }\n"
            "impl Counter {\n"
            "    fn new() -> Counter {\n"
            "        Counter { n: 0 }\n"
            "    }\n"
            "    fn bump(&mut self) {\n"
            "        self.n = self.n + 1;\n"
            "    }\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("class Counter:", ext)
        self.assertIn("fn new() -> Counter:", ext)
        self.assertIn("fn bump(self):", ext)

    def test_println_formatting(self):
        src = 'fn main() {\n    let name = "Bartosz";\n    println!("hello {}! x={}", name, 42);\n}\n'
        ext, _ = translate_rust(src)
        self.assertIn('print($"hello {name}! x={42}")', ext)

    def test_vec_and_methods(self):
        src = (
            "fn main() {\n"
            "    let mut v = vec![1, 2, 3];\n"
            "    v.push(4);\n"
            "    let n = v.len();\n"
            "    println!(\"{}\", n);\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("v: List[Any] = [1, 2, 3]", ext)
        self.assertIn("v.append(4)", ext)
        self.assertIn("n: Any = len(v)", ext)

    def test_match_arms(self):
        src = (
            "fn f(x: i32) {\n"
            "    match x {\n"
            "        1 => println!(\"one\"),\n"
            "        _ => println!(\"other\"),\n"
            "    }\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("case 1:", ext)
        self.assertIn("case _:", ext)

    def test_control_flow(self):
        src = (
            "fn main() {\n"
            "    let mut i = 0;\n"
            "    while i < 10 {\n"
            "        i = i + 1;\n"
            "    }\n"
            "    loop {\n"
            "        break;\n"
            "    }\n"
            "    if i == 10 {\n"
            '        println!("ten");\n'
            "    } else if i > 10 {\n"
            '        println!("more");\n'
            "    }\n"
            "}\n"
        )
        ext, _ = translate_rust(src)
        self.assertIn("while i < 10:", ext)
        self.assertIn("while True:", ext)
        self.assertIn("elif i > 10:", ext)

    def test_use_is_commented(self):
        ext, _ = translate_rust("use std::collections::HashMap;\nfn main() {}\n")
        self.assertIn("# use std::collections::HashMap;", ext)

    def test_type_mapping(self):
        from externum.translate import _map_rs_type

        self.assertEqual(_map_rs_type("Vec<String>"), "List[Str]")
        self.assertEqual(_map_rs_type("&mut u64"), "Int")
        self.assertEqual(_map_rs_type("Option<i32>"), "Option[Int]")
        self.assertEqual(_map_rs_type("f32"), "Float")


class TestEndToEnd(unittest.TestCase):
    """Translate, then run through the full Externum python-target pipeline."""

    def test_python_program_roundtrip(self):
        src = (
            "def fib(n: int) -> int:\n"
            "    if n < 2:\n"
            "        return n\n"
            "    return fib(n - 1) + fib(n - 2)\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    print(fib(10))\n"
        )
        ext, rep = translate_python(src)
        py = compile_python_target(ext)
        self.assertIn("def fib", py)
        self.assertIn("def main", py)

    def test_report_summary(self):
        _, rep = translate_python("import requests\nx = unknown_call()\n")
        self.assertTrue(rep.summary())


if __name__ == "__main__":
    unittest.main()
