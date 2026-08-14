"""Tests for Externum strict-language analysis.

Externum is strict by design — there is no relaxed mode. These tests cover:
macro expansion, `match`/`case`, manual memory management (`alloc`/`free`/`@`),
static typing + mandatory declarations, immutability (`mut`), move semantics
(use-after-move), ownership enforcement, `trait`/`impl`, `unsafe` escape
hatch, esoteric operators (≠, ≈, ←) and concurrency
(`spawn`/`chan`/`send`/`recv`).
"""

import contextlib
import io
import unittest

from externum.runtime import Runtime
from externum.analysis import preprocess, MacroError
from externum.typesys import ExternumTypeError

RT = Runtime()


def run_strict(src: str) -> dict:
    """Run a program (strict language) with stdout captured into ns['_printed']."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ns = RT.run(src)
    ns['_printed'] = buf.getvalue().splitlines()
    return ns


class TestMacros(unittest.TestCase):
    def test_macro_expansion_runs(self):
        src = """
macro DOUBLE(x) {
    (x) * 2
}
def main():
    print(DOUBLE(21))
main()
"""
        ns = run_strict(src)
        self.assertIn('42', ns['_printed'])

    def test_macro_preprocess_output(self):
        src = """
macro SQ(x) {
    (x) * (x)
}
def main():
    v: Int = SQ(7)
main()
"""
        processed, macros = preprocess(src)
        self.assertIn('SQ', macros)
        self.assertIn('(7) * (7)', processed)
        self.assertNotIn('macro SQ', processed)

    def test_macro_wrong_arg_count_raises(self):
        src = """
macro ADD(a, b) {
    (a) + (b)
}
def main():
    print(ADD(1))
main()
"""
        with self.assertRaises(MacroError):
            preprocess(src)

    def test_macro_zero_param(self):
        src = """
macro ANSWER {
    42
}
def main():
    print(ANSWER())
main()
"""
        ns = run_strict(src)
        self.assertIn('42', ns['_printed'])


class TestMatch(unittest.TestCase):
    def test_match_literals_and_wildcard(self):
        src = """
def main():
    v: Int = 2
    match v:
        case 1:
            print('one')
        case 2:
            print('two')
        case _:
            print('other')
main()
"""
        ns = run_strict(src)
        self.assertIn('two', ns['_printed'])

    def test_match_binds_and_guard(self):
        src = """
def main():
    v: Int = 5
    match v:
        case 1:
            print('one')
        case n if n > 3:
            print('big:', n)
        case _:
            print('other')
main()
"""
        ns = run_strict(src)
        self.assertIn('big: 5', ns['_printed'])

    def test_match_list_destructure(self):
        src = """
def main():
    pair: List[Int] = [10, 20]
    match pair:
        case [a, b]:
            print('sum:', a + b)
        case _:
            print('no')
main()
"""
        ns = run_strict(src)
        self.assertIn('sum: 30', ns['_printed'])

    def test_match_string_literal(self):
        src = """
def main():
    s: Str = 'hello'
    match s:
        case 'hello':
            print('greeted')
        case _:
            print('unknown')
main()
"""
        ns = run_strict(src)
        self.assertIn('greeted', ns['_printed'])

    def test_match_no_case_matches_raises(self):
        src = """
def main():
    v: Int = 99
    match v:
        case 1:
            print('one')
main()
"""
        with self.assertRaises(RuntimeError):
            run_strict(src)


class TestManualMemory(unittest.TestCase):
    def test_alloc_store_load_free(self):
        src = """
def main():
    p: Ptr[Int] = alloc(Int)
    @p = 42
    print(@p)
    free(p)
main()
"""
        ns = run_strict(src)
        self.assertIn('42', ns['_printed'])

    def test_alloc_multi_slot(self):
        src = """
def main():
    p: Ptr[Int] = alloc(Int, 3)
    @p = 7
    print(@p)
    free(p)
main()
"""
        ns = run_strict(src)
        self.assertIn('7', ns['_printed'])

    def test_double_free_rejected_at_compile_time(self):
        src = """
def main():
    p: Ptr[Int] = alloc(Int)
    free(p)
    free(p)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('double free', str(ctx.exception))

    def test_use_after_free_rejected(self):
        src = """
def main():
    p: Ptr[Int] = alloc(Int)
    free(p)
    print(@p)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('use-after-free', str(ctx.exception))

    def test_deref_of_non_pointer_rejected(self):
        src = """
def main():
    x: Int = 5
    print(@x)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('not a Ptr', str(ctx.exception))

    def test_free_of_undeclared_pointer_rejected(self):
        src = """
def main():
    free(not_a_ptr)
main()
"""
        with self.assertRaises(ExternumTypeError):
            run_strict(src)

    def test_free_runtime_error_on_unknown_pointer(self):
        # even inside `unsafe:` (checks skipped) the runtime itself
        # rejects unknown pointer ids
        src = """
def main():
    unsafe:
        free(12345)
main()
"""
        with self.assertRaises(RuntimeError):
            run_strict(src)


class TestTypeChecker(unittest.TestCase):
    def test_undeclared_variable_rejected(self):
        src = """
def main():
    print(x)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('undeclared', str(ctx.exception))

    def test_type_mismatch_rejected(self):
        src = """
def main():
    mut x: Int = 5
    x = 'nope'
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('cannot assign', str(ctx.exception))

    def test_annotated_assignment_ok(self):
        src = """
def main():
    x: Int = 5
    y: Str = 'ok'
    print(x, y)
main()
"""
        ns = run_strict(src)
        self.assertIn('5 ok', ns['_printed'])

    def test_int_does_not_widen_to_float(self):
        # strict: no implicit Int -> Float conversion
        src = """
def main():
    f: Float = 1
    print(f)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('cannot assign', str(ctx.exception))

    def test_float_literal_ok(self):
        src = """
def main():
    f: Float = 1.0
    print(f)
main()
"""
        ns = run_strict(src)
        self.assertIn('1.0', ns['_printed'])

    def test_bool_expression_type(self):
        src = """
def main():
    b: Bool = 1 < 2
    print(b)
main()
"""
        ns = run_strict(src)
        self.assertIn('True', ns['_printed'])

    def test_function_return_type_mismatch(self):
        src = """
def f() -> Int:
    return 'oops'

def main():
    print(f())
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('return type', str(ctx.exception))

    def test_function_return_type_ok(self):
        src = """
def add(a: Int, b: Int) -> Int:
    return a + b

def main():
    print(add(2, 3))
main()
"""
        ns = run_strict(src)
        self.assertIn('5', ns['_printed'])

    def test_param_without_annotation_rejected(self):
        src = """
def f(x):
    return x
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('needs a type annotation', str(ctx.exception))

    def test_star_param_without_annotation_ok(self):
        src = """
def total(*nums) -> Int:
    mut s: Int = 0
    for n in nums:
        s = s + n
    return s

def main():
    print(total(1, 2, 3))
main()
"""
        ns = run_strict(src)
        self.assertIn('6', ns['_printed'])


class TestImmutability(unittest.TestCase):
    def test_reassign_immutable_rejected(self):
        src = """
def main():
    x: Int = 5
    x = 6
    print(x)
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('immutable', str(ctx.exception))

    def test_mut_allows_reassign(self):
        src = """
def main():
    mut x: Int = 5
    x = 6
    print(x)
main()
"""
        ns = run_strict(src)
        self.assertIn('6', ns['_printed'])

    def test_aug_assign_needs_mut(self):
        src = """
def main():
    x: Int = 5
    x += 1
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('immutable', str(ctx.exception))


class TestMoveSemantics(unittest.TestCase):
    def test_use_after_move_rejected(self):
        src = """
def consume(xs: List[Int]) -> Int:
    return len(xs)

def main():
    data: List[Int] = [1, 2, 3]
    consume(data)
    print(len(data))
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('moved', str(ctx.exception))

    def test_copy_restores_value(self):
        src = """
def consume(xs: List[Int]) -> Int:
    return len(xs)

def main():
    data: List[Int] = [1, 2, 3]
    n: Int = consume(copy(data))
    print(n, len(data))
main()
"""
        ns = run_strict(src)
        self.assertIn('3 3', ns['_printed'])

    def test_scalar_assignment_is_copy(self):
        src = """
def main():
    a: Int = 5
    b: Int = a
    print(a, b)
main()
"""
        # Int is a copy type — no move, so `a` stays usable after `b = a`
        ns = run_strict(src)
        self.assertIn('5 5', ns['_printed'])


class TestTraits(unittest.TestCase):
    def test_trait_impl_satisfies(self):
        src = """
trait Speaker:
    def speak(self) -> Str:
        pass

class Dog:
    def speak(self) -> Str:
        return 'woof'

impl Speaker for Dog:
    def speak(self) -> Str:
        return 'woof-impl'

def main():
    d: Dog = Dog()
    print(d.speak())
main()
"""
        ns = run_strict(src)
        self.assertIn('woof-impl', ns['_printed'])

    def test_impl_missing_method_rejected(self):
        src = """
trait Speaker:
    def speak(self) -> Str:
        pass

class Dog:
    pass

impl Speaker for Dog:
    def wag(self) -> Void:
        pass

def main():
    pass
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('missing method', str(ctx.exception))

    def test_impl_unknown_trait_rejected(self):
        src = """
class Dog:
    pass

impl NotATrait for Dog:
    def m(self) -> Void:
        pass

def main():
    pass
main()
"""
        with self.assertRaises(ExternumTypeError) as ctx:
            run_strict(src)
        self.assertIn('unknown trait', str(ctx.exception))


class TestUnsafe(unittest.TestCase):
    def test_unsafe_bypasses_checks(self):
        src = """
def main():
    unsafe:
        x = 1
        print(x)
main()
"""
        ns = run_strict(src)
        self.assertIn('1', ns['_printed'])

    def test_unsafe_allows_undeclared(self):
        src = """
def main():
    unsafe:
        ghost = 'not declared anywhere'
        print(ghost)
main()
"""
        ns = run_strict(src)
        self.assertIn('not declared anywhere', ns['_printed'])


class TestEsotericOperators(unittest.TestCase):
    def test_neq_and_eq(self):
        src = """
def main():
    print(1 ≠ 2)
    print(2 ≈ 2)
main()
"""
        ns = run_strict(src)
        self.assertEqual(ns['_printed'], ['True', 'True'])

    def test_left_arrow_assignment(self):
        src = """
def main():
    mut x: Int = 1
    x ← 7
    print(x)
main()
"""
        ns = run_strict(src)
        self.assertIn('7', ns['_printed'])


class TestConcurrency(unittest.TestCase):
    def test_spawn_send_recv(self):
        src = """
def worker(ch: Any) -> Void:
    send(ch, 123)

def main():
    ch: Any = chan()
    spawn(worker(ch))
    print(recv(ch))
main()
"""
        ns = run_strict(src)
        self.assertIn('123', ns['_printed'])


if __name__ == '__main__':
    unittest.main()
