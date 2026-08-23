"""Externum v4 — comprehensive tests for the new bytecode compiler, VM,
algebraic types, struct/enum, pipe operator, defer, loop, and more.

Run with:  python3 -m unittest tests/test_v4.py -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum import Lexer, Parser, BytecodeCompiler, VM


def run_vm(source, argv=None):
    """Compile source to bytecode and run via VM. Returns stdout."""
    out = io.StringIO()
    vm = VM(stdout=out, argv=argv or [])
    vm.run_source(source)
    return out.getvalue()


def compile_to_bytecode(source):
    """Compile source to bytecode module."""
    tokens = Lexer(source).tokenize()
    ast = list(Parser(tokens).parse())
    compiler = BytecodeCompiler(ast)
    return compiler.compile()


# ════════════════════════════════════════════════════════════════════════
# LEXER v4 tests
# ════════════════════════════════════════════════════════════════════════
class TestLexerV4(unittest.TestCase):
    def test_octal_literal(self):
        toks = Lexer("x = 0o77\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('OCTAL_NUMBER', types)

    def test_char_literal(self):
        toks = Lexer("c = 'a'\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('CHAR', types)

    def test_new_keywords(self):
        src = "struct enum mod use async await effect region type where const static ref deref loop defer comptime let pub priv\n"
        types = {t.type for t in Lexer(src).tokenize()}
        for kw in ('STRUCT', 'ENUM', 'MOD', 'USE', 'ASYNC', 'AWAIT',
                    'EFFECT', 'REGION', 'TYPE', 'WHERE', 'CONST', 'STATIC',
                    'REF', 'DEREF', 'LOOP', 'DEFER', 'COMPTIME', 'LET',
                    'PUB', 'PRIV'):
            self.assertIn(kw, types)

    def test_pipe_operator(self):
        toks = Lexer("x |> f\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('PIPE', types)

    def test_fat_arrow(self):
        toks = Lexer("f = x => x + 1\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('FAT_ARROW', types)

    def test_nullish_operator(self):
        toks = Lexer("x = a ?? b\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('NULLISH', types)

    def test_optional_chain(self):
        toks = Lexer("x = a?.b\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('OPTIONAL_CHAIN', types)

    def test_colon_colon(self):
        toks = Lexer("x = std::io\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('COLON_COLON', types)

    def test_range_operators(self):
        toks = Lexer("r = 0..10\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('DOTDOT', types)
        toks = Lexer("r = 0..=10\n").tokenize()
        types = {t.type for t in toks}
        self.assertIn('DOTDOT_EQ', types)


# ════════════════════════════════════════════════════════════════════════
# PARSER v4 tests
# ════════════════════════════════════════════════════════════════════════
class TestParserV4(unittest.TestCase):
    def parse(self, source):
        return list(Parser(Lexer(source).tokenize()).parse())

    def test_struct_def(self):
        ast = self.parse("struct Point:\n    x: Int\n    y: Int\n")
        self.assertEqual(ast[0].type, "STRUCT")
        self.assertEqual(ast[0].value, "Point")
        self.assertEqual(len(ast[0].children), 2)

    def test_struct_def_braces(self):
        ast = self.parse("struct Point { x: Int, y: Int }\n")
        self.assertEqual(ast[0].type, "STRUCT")
        self.assertEqual(ast[0].value, "Point")
        self.assertEqual(len(ast[0].children), 2)

    def test_enum_def(self):
        ast = self.parse("enum Result:\n    Ok\n    Err\n")
        self.assertEqual(ast[0].type, "ENUM")
        self.assertEqual(ast[0].value, "Result")
        self.assertEqual(len(ast[0].children), 2)

    def test_enum_with_data(self):
        ast = self.parse("enum Option:\n    Some(T)\n    None\n")
        self.assertEqual(ast[0].type, "ENUM")
        variants = [c.value for c in ast[0].children if c.type == 'VARIANT']
        self.assertIn('Some', variants)
        self.assertIn('None', variants)

    def test_const_def(self):
        ast = self.parse("const PI = 3.14\n")
        self.assertEqual(ast[0].type, "CONST")
        self.assertEqual(ast[0].value, "PI")

    def test_static_def(self):
        ast = self.parse("static mut COUNTER = 0\n")
        self.assertEqual(ast[0].type, "STATIC")

    def test_loop_stmt(self):
        ast = self.parse("loop:\n    print('hello')\n")
        self.assertEqual(ast[0].type, "LOOP")

    def test_defer_stmt(self):
        ast = self.parse("defer:\n    print('cleanup')\n")
        self.assertEqual(ast[0].type, "DEFER")

    def test_type_alias(self):
        ast = self.parse("type Func = fn(Int) -> Int\n")
        self.assertEqual(ast[0].type, "TYPE_ALIAS")
        self.assertEqual(ast[0].value, "Func")

    def test_mod_def(self):
        ast = self.parse("mod utils:\n    pass\n")
        self.assertEqual(ast[0].type, "MOD")
        self.assertEqual(ast[0].value, "utils")

    def test_match_statement(self):
        ast = self.parse("match x:\n    case 1:\n        print('one')\n    case _:\n        print('other')\n")
        self.assertEqual(ast[0].type, "MATCH")


# ════════════════════════════════════════════════════════════════════════
# BYTECODE COMPILER tests
# ════════════════════════════════════════════════════════════════════════
class TestBytecodeCompiler(unittest.TestCase):
    def test_compile_simple(self):
        module = compile_to_bytecode("x = 42\n")
        self.assertIsNotNone(module)
        self.assertEqual(module.name, '<main>')

    def test_compile_function(self):
        module = compile_to_bytecode("def add(a, b):\n    return a + b\n")
        self.assertEqual(len(module.functions), 1)
        self.assertEqual(module.functions[0].name, 'add')

    def test_compile_class(self):
        module = compile_to_bytecode("class Dog:\n    def bark(self):\n        return 'woof'\n")
        self.assertIsNotNone(module)

    def test_compile_struct(self):
        module = compile_to_bytecode("struct Point:\n    x: Int\n    y: Int\n")
        self.assertIn('Point', module.structs)

    def test_compile_enum(self):
        module = compile_to_bytecode("enum Color:\n    Red\n    Green\n    Blue\n")
        self.assertIn('Color', module.enums)

    def test_compile_const(self):
        module = compile_to_bytecode("const MAX = 100\n")
        self.assertIsNotNone(module)

    def test_compile_trait(self):
        module = compile_to_bytecode("trait Speaker:\n    def speak(self) -> Str:\n        pass\n")
        self.assertIn('Speaker', module.traits)


# ════════════════════════════════════════════════════════════════════════
# VM tests — basic operations
# ════════════════════════════════════════════════════════════════════════
class TestVMBasic(unittest.TestCase):
    def test_hello_world(self):
        out = run_vm('print("Hello from EXBC VM!")\n')
        self.assertIn("Hello from EXBC VM!", out)

    def test_arithmetic(self):
        out = run_vm("print(2 + 3)\n")
        self.assertIn("5", out)

    def test_subtraction(self):
        out = run_vm("print(10 - 4)\n")
        self.assertIn("6", out)

    def test_multiplication(self):
        out = run_vm("print(6 * 7)\n")
        self.assertIn("42", out)

    def test_division(self):
        out = run_vm("print(10 / 2)\n")
        self.assertIn("5.0", out)

    def test_floor_division(self):
        out = run_vm("print(7 // 2)\n")
        self.assertIn("3", out)

    def test_modulo(self):
        out = run_vm("print(7 % 2)\n")
        self.assertIn("1", out)

    def test_power(self):
        out = run_vm("print(2 ** 8)\n")
        self.assertIn("256", out)

    def test_negative(self):
        out = run_vm("print(-5)\n")
        self.assertIn("-5", out)

    def test_string_literal(self):
        out = run_vm('print("abc")\n')
        self.assertIn("abc", out)

    def test_bool_true(self):
        out = run_vm("print(True)\n")
        self.assertIn("True", out)

    def test_bool_false(self):
        out = run_vm("print(False)\n")
        self.assertIn("False", out)

    def test_none_literal(self):
        out = run_vm("print(None)\n")
        self.assertIn("None", out)

    def test_comparison_eq(self):
        out = run_vm("print(5 == 5)\n")
        self.assertIn("True", out)

    def test_comparison_neq(self):
        out = run_vm("print(5 != 3)\n")
        self.assertIn("True", out)

    def test_comparison_lt(self):
        out = run_vm("print(3 < 5)\n")
        self.assertIn("True", out)

    def test_comparison_gt(self):
        out = run_vm("print(5 > 3)\n")
        self.assertIn("True", out)

    def test_comparison_lte(self):
        out = run_vm("print(5 <= 5)\n")
        self.assertIn("True", out)

    def test_comparison_gte(self):
        out = run_vm("print(5 >= 3)\n")
        self.assertIn("True", out)

    def test_and_operator(self):
        out = run_vm("print(True and False)\n")
        self.assertIn("False", out)

    def test_or_operator(self):
        out = run_vm("print(True or False)\n")
        self.assertIn("True", out)

    def test_not_operator(self):
        out = run_vm("print(not True)\n")
        self.assertIn("False", out)

    def test_bitwise(self):
        out = run_vm("print(0b1100 & 0b1010)\n")
        self.assertIn("8", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — variables and control flow
# ════════════════════════════════════════════════════════════════════════
class TestVMVariables(unittest.TestCase):
    def test_variable_assignment(self):
        out = run_vm("x = 42\nprint(x)\n")
        self.assertIn("42", out)

    def test_variable_reassignment(self):
        out = run_vm("x = 1\nx = 2\nprint(x)\n")
        self.assertIn("2", out)

    def test_multiple_variables(self):
        out = run_vm("a = 10\nb = 20\nprint(a + b)\n")
        self.assertIn("30", out)

    def test_if_true(self):
        out = run_vm("x = 10\nif x > 5:\n    print('big')\n")
        self.assertIn("big", out)

    def test_if_false(self):
        out = run_vm("x = 1\nif x > 5:\n    print('big')\nelse:\n    print('small')\n")
        self.assertIn("small", out)

    def test_if_elif_else(self):
        out = run_vm("x = 5\nif x > 10:\n    print('big')\nelif x > 3:\n    print('mid')\nelse:\n    print('small')\n")
        self.assertIn("mid", out)

    def test_while_loop(self):
        out = run_vm("i = 0\nwhile i < 3:\n    print(i)\n    i = i + 1\n")
        lines = out.strip().split('\n')
        self.assertEqual(lines, ['0', '1', '2'])

    def test_for_range(self):
        out = run_vm("for i in range(3):\n    print(i)\n")
        lines = out.strip().split('\n')
        self.assertEqual(lines, ['0', '1', '2'])

    def test_list_literal(self):
        out = run_vm("xs = [1, 2, 3]\nprint(xs[0])\nprint(xs[2])\n")
        self.assertIn("1", out)
        self.assertIn("3", out)

    def test_list_length(self):
        out = run_vm("xs = [1, 2, 3]\nprint(len(xs))\n")
        self.assertIn("3", out)

    def test_string_length(self):
        out = run_vm('print(len("hello"))\n')
        self.assertIn("5", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — functions
# ════════════════════════════════════════════════════════════════════════
class TestVMFunctions(unittest.TestCase):
    def test_simple_function(self):
        out = run_vm("def greet():\n    print('hi')\ngreet()\n")
        self.assertIn("hi", out)

    def test_function_with_args(self):
        out = run_vm("def add(a, b):\n    return a + b\nprint(add(3, 4))\n")
        self.assertIn("7", out)

    def test_function_with_default(self):
        out = run_vm("def greet(name='world'):\n    print(name)\ngreet()\n")
        self.assertIn("world", out)

    def test_recursion(self):
        out = run_vm("def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(5))\n")
        self.assertIn("120", out)

    def test_nested_calls(self):
        out = run_vm("def double(x):\n    return x * 2\ndef triple(x):\n    return x * 3\nprint(double(triple(5)))\n")
        self.assertIn("30", out)

    def test_lambda(self):
        out = run_vm("f = lambda x, y: x + y\nprint(f(3, 4))\n")
        self.assertIn("7", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — NV4.0 algebraic types
# ════════════════════════════════════════════════════════════════════════
class TestVMAlgebraicTypes(unittest.TestCase):
    def test_ok_result(self):
        out = run_vm("r = Ok(42)\nprint(r)\n")
        self.assertIn("Ok(42)", out)

    def test_err_result(self):
        out = run_vm("r = Err('oops')\nprint(r)\n")
        self.assertIn("Err('oops')", out)

    def test_some_option(self):
        out = run_vm("o = Some(42)\nprint(o)\n")
        self.assertIn("Some(42)", out)

    def test_none_option(self):
        out = run_vm("o = Option.None()\nprint(o)\n")
        self.assertIn("None", out)

    def test_result_unwrap(self):
        out = run_vm("r = Ok(42)\nprint(r.unwrap())\n")
        self.assertIn("42", out)

    def test_option_unwrap(self):
        out = run_vm("o = Some(42)\nprint(o.unwrap())\n")
        self.assertIn("42", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — builtins
# ════════════════════════════════════════════════════════════════════════
class TestVMBuiltins(unittest.TestCase):
    def test_len_string(self):
        out = run_vm('print(len("hello"))\n')
        self.assertIn("5", out)

    def test_len_list(self):
        out = run_vm("print(len([1, 2, 3]))\n")
        self.assertIn("3", out)

    def test_str_conversion(self):
        out = run_vm("print(str(42))\n")
        self.assertIn("42", out)

    def test_int_conversion(self):
        out = run_vm("print(int('42'))\n")
        self.assertIn("42", out)

    def test_float_conversion(self):
        out = run_vm("print(float(42))\n")
        self.assertIn("42.0", out)

    def test_bool_conversion(self):
        out = run_vm("print(bool(1))\n")
        self.assertIn("True", out)

    def test_type_check(self):
        out = run_vm("print(type(42))\n")
        self.assertIn("int", out)

    def test_isinstance(self):
        out = run_vm("print(isinstance(42, int))\n")
        self.assertIn("True", out)

    def test_min_max(self):
        out = run_vm("print(min(3, 1, 2))\nprint(max(3, 1, 2))\n")
        self.assertIn("1", out)
        self.assertIn("3", out)

    def test_abs(self):
        out = run_vm("print(abs(-5))\n")
        self.assertIn("5", out)

    def test_round(self):
        out = run_vm("print(round(3.7))\n")
        self.assertIn("4", out)

    def test_hex(self):
        out = run_vm("print(hex(255))\n")
        self.assertIn("0xff", out)

    def test_bin(self):
        out = run_vm("print(bin(10))\n")
        self.assertIn("0b1010", out)

    def test_oct(self):
        out = run_vm("print(oct(8))\n")
        self.assertIn("0o10", out)

    def test_chr_ord(self):
        out = run_vm("print(chr(65))\nprint(ord('A'))\n")
        self.assertIn("A", out)
        self.assertIn("65", out)

    def test_sorted(self):
        out = run_vm("print(sorted([3, 1, 2]))\n")
        self.assertIn("[1, 2, 3]", out)

    def test_enumerate(self):
        out = run_vm("for i, v in enumerate(['a', 'b']):\n    print(i, v)\n")
        self.assertIn("0 a", out)
        self.assertIn("1 b", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — error handling
# ════════════════════════════════════════════════════════════════════════
class TestVMErrors(unittest.TestCase):
    def test_panic(self):
        with self.assertRaises(Exception):
            run_vm("panic('boom')\n")

    def test_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            run_vm("print(1 / 0)\n")

    def test_undefined_variable(self):
        with self.assertRaises(Exception):
            run_vm("print(nonexistent)\n")

    def test_index_out_of_range(self):
        with self.assertRaises(IndexError):
            run_vm("xs = [1, 2]\nprint(xs[10])\n")


# ════════════════════════════════════════════════════════════════════════
# VM tests — memory management
# ════════════════════════════════════════════════════════════════════════
class TestVMMemory(unittest.TestCase):
    def test_alloc_free(self):
        out = run_vm("p = alloc(42)\nprint(p)\nfree(p)\n")
        self.assertIn("1", out)  # first allocated pointer id

    def test_alloc_and_load(self):
        out = run_vm("p = alloc(42)\nprint(sizeof('Int'))\nfree(p)\n")
        self.assertIn("8", out)


# ════════════════════════════════════════════════════════════════════════
# VM tests — string operations
# ════════════════════════════════════════════════════════════════════════
class TestVMStrings(unittest.TestCase):
    def test_string_concatenation(self):
        out = run_vm('print("hello" + " " + "world")\n')
        self.assertIn("hello world", out)

    def test_string_repetition(self):
        out = run_vm('print("ab" * 3)\n')
        self.assertIn("ababab", out)

    def test_string_index(self):
        out = run_vm('s = "hello"\nprint(s[0])\nprint(s[4])\n')
        self.assertIn("h", out)
        self.assertIn("o", out)


# ════════════════════════════════════════════════════════════════════════
# Full pipeline integration tests
# ════════════════════════════════════════════════════════════════════════
class TestIntegration(unittest.TestCase):
    def test_fibonacci(self):
        source = """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(10))
"""
        out = run_vm(source)
        self.assertIn("55", out)

    def test_hello_class(self):
        source = """
class Greeter:
    def __init__(self, name):
        self.name = name
    def greet(self):
        return "Hello, " + self.name

g = Greeter("World")
print(g.greet())
"""
        out = run_vm(source)
        self.assertIn("Hello, World", out)

    def test_nested_loops(self):
        source = """
result = 0
for i in range(3):
    for j in range(3):
        result = result + 1
print(result)
"""
        out = run_vm(source)
        self.assertIn("9", out)

    def test_closure(self):
        source = """
def make_adder(n):
    def adder(x):
        return x + n
    return adder

add5 = make_adder(5)
print(add5(10))
"""
        out = run_vm(source)
        self.assertIn("15", out)

    def test_match_pattern(self):
        source = """
x = 2
match x:
    case 1:
        print('one')
    case 2:
        print('two')
    case _:
        print('other')
"""
        out = run_vm(source)
        self.assertIn("two", out)

    def test_struct_creation(self):
        source = """
struct Point:
    x: Int
    y: Int
p = Point(3, 4)
print(p)
"""
        out = run_vm(source)
        self.assertIn("Point", out)

    def test_enum_creation(self):
        source = """
enum Color:
    Red
    Green
    Blue
c = Color.Red()
print(c)
"""
        out = run_vm(source)
        self.assertIn("Red", out)

    def test_result_ok_err(self):
        source = """
def divide(a, b):
    if b == 0:
        return Err('division by zero')
    return Ok(a / b)

r = divide(10, 2)
print(r)
r2 = divide(10, 0)
print(r2)
"""
        out = run_vm(source)
        self.assertIn("Ok(5.0)", out)
        self.assertIn("Err('division by zero')", out)

    def test_const_and_static(self):
        source = """
const PI = 3.14159
print(PI)
"""
        out = run_vm(source)
        self.assertIn("3.14159", out)

    def test_loop_with_break(self):
        source = """
i = 0
while True:
    if i >= 5:
        break
    print(i)
    i = i + 1
"""
        out = run_vm(source)
        lines = out.strip().split('\n')
        self.assertEqual(lines, ['0', '1', '2', '3', '4'])

    def test_modular_code(self):
        source = """
mod math:
    pass
print('mod loaded')
"""
        out = run_vm(source)
        self.assertIn("mod loaded", out)

    def test_trait_declaration(self):
        source = """
trait Drawable:
    def draw(self) -> str:
        pass
print('trait declared')
"""
        out = run_vm(source)
        self.assertIn("trait declared", out)

    def test_list_operations(self):
        source = """
xs = [1, 2, 3, 4, 5]
print(len(xs))
print(xs[0] + xs[4])
"""
        out = run_vm(source)
        self.assertIn("5", out)
        self.assertIn("6", out)

    def test_dict_operations(self):
        source = """
d = {"a": 1, "b": 2}
print(d["a"])
"""
        out = run_vm(source)
        self.assertIn("1", out)

    def test_tuple_literal(self):
        source = """
t = (1, 2, 3)
print(t[0])
print(t[2])
"""
        out = run_vm(source)
        self.assertIn("1", out)
        self.assertIn("3", out)

    def test_complex_expression(self):
        source = """
x = 10
y = 20
z = x + y * 3 - x // 2
print(z)
"""
        out = run_vm(source)
        self.assertIn("65", out)


if __name__ == '__main__':
    unittest.main()
