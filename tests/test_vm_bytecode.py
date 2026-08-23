"""VM bytecode compiler tests — runs in CI as a separate script."""
import io
import sys
import unittest

from externum.lexer import Lexer
from externum.parser import Parser
from externum.bytecode import BytecodeCompiler
from externum.vm import VM


def _run_vm(code: str) -> str:
    tokens = Lexer(code).tokenize()
    ast = list(Parser(tokens).parse())
    compiler = BytecodeCompiler(ast)
    module = compiler.compile()
    vm = VM()
    buf = io.StringIO()
    vm._stdout = buf
    vm.run_module(module)
    return buf.getvalue().strip()


class TestVMBytecode(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(_run_vm("print(2 + 3 * 4)"), "14")

    def test_ternary(self):
        self.assertEqual(_run_vm('print("yes" if True else "no")'), "yes")

    def test_function(self):
        code = "def add(a, b):\n    return a + b\nprint(add(2, 3))"
        self.assertEqual(_run_vm(code), "5")

    def test_while_loop(self):
        code = "i = 0\nwhile i < 5:\n    i = i + 1\nprint(i)"
        self.assertEqual(_run_vm(code), "5")

    def test_list_index(self):
        code = "a = [1, 2, 3]\nprint(a[1])"
        self.assertEqual(_run_vm(code), "2")

    def test_import(self):
        code = 'import os\nprint("import ok")'
        self.assertEqual(_run_vm(code), "import ok")


if __name__ == "__main__":
    unittest.main()
