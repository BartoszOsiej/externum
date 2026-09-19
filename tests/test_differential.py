"""Differential backend testing — one program, three backends, one answer.

Born from a Mastodon thread (@kyisaiah47 asked whether the benchmark's
bug discovery was differential testing; the honest answer was "accidentally
yes, so now it is by design"). Both historical VM bugs (silent infinite
loop on augmented assignment; parenthesized RHS compiled as an identifier)
lived ONLY in the bytecode path while Python and Bash agreed — exactly the
backend-drift class this harness catches.

Two tiers:

1. CONSENSUS — cases where all three backends already agree. Any
   regression (a backend starts diverging) fails the suite immediately.
2. KNOWN DRIFT — tracked divergence with an open issue. Written with
   @unittest.expectedFailure so a suite run is green while the drift
   exists. The moment a backend is fixed, the test XPASSes and the
   grader fails the run — forcing the case to be promoted to tier 1.
   Drift can only ever shrink.

First harvest (day one): untyped ``mut`` never binds the variable (#23),
VM f-strings return the literal template (#24), bash backend silently
drops expression-bearing print/assignment RHS (#25).
"""

import io
import os
import signal
import subprocess
import sys
import tempfile
import unittest

from externum.bash_backend import BashCodegen
from externum.bytecode import BytecodeCompiler
from externum.lexer import Lexer
from externum.parser import Parser
from externum.runtime import Runtime
from externum.vm import VM

VM_TIMEOUT_S = 15
BASH_TIMEOUT_S = 15


def _run_python(code: str) -> str:
    """Front-end -> Python transpiler -> execute under CPython."""
    rt = Runtime()
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rt.run(code)
    finally:
        sys.stdout = old
    return buf.getvalue().strip()


def _run_vm(code: str) -> str:
    """Front-end -> BytecodeCompiler -> VM, with hang protection."""

    def _exec():
        tokens = Lexer(code).tokenize()
        ast = list(Parser(tokens).parse())
        module = BytecodeCompiler(ast).compile()
        vm = VM()
        buf = io.StringIO()
        vm._stdout = buf
        vm.run_module(module)
        return buf.getvalue().strip()

    if hasattr(signal, "SIGALRM"):

        class _Hang(TimeoutError):
            pass

        def _alarm(signum, frame):
            raise _Hang("VM hang (regression of the silent-infinite-loop bug class)")

        old = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(VM_TIMEOUT_S)
        try:
            return _exec()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    return _exec()


def _run_bash(code: str) -> str:
    """Front-end -> BashCodegen -> real bash subprocess."""
    tokens = Lexer(code).tokenize()
    ast = list(Parser(tokens).parse())
    script, _warnings = BashCodegen(ast).generate()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(script)
        path = fh.name
    try:
        proc = subprocess.run(  # noqa: S603 — runs our own generated script from a private tmp file
            ["/bin/bash", path], capture_output=True, text=True, timeout=BASH_TIMEOUT_S
        )
    finally:
        os.unlink(path)
    if proc.returncode != 0:
        raise AssertionError(f"bash backend exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


# ─── Tier 1: consensus — all three backends must agree ─────────────────────
CONSENSUS_CASES = [
    ("arithmetic", "print(2 + 3 * 4)", "14"),
    ("strings", 'print("hello" + " " + "world")', "hello world"),
    ("while-loop", "i = 0\nwhile i < 5:\n    i = i + 1\nprint(i)", "5"),
    ("recursion", "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(6))", "720"),
    ("modulo", "print(17 % 5)", "2"),
]


class TestConsensus(unittest.TestCase):
    """All three backends must produce IDENTICAL output on every case."""

    def _assert_all_backends(self, name: str, code: str, expected: str):
        results = {}
        for backend, runner in (("python", _run_python), ("vm", _run_vm), ("bash", _run_bash)):
            try:
                results[backend] = runner(code)
            except Exception as e:
                results[backend] = f"<{backend} ERROR: {e}>"
        diverged = {b: o for b, o in results.items() if o != expected}
        self.assertFalse(
            diverged,
            f"backend drift on case '{name}': expected {expected!r}, "
            f"got {diverged!r} (agreeing: "
            f"{ {b: o for b, o in results.items() if o == expected} })",
        )

    def test_consensus_cases_all_backends_agree(self):
        for name, code, expected in CONSENSUS_CASES:
            with self.subTest(case=name):
                self._assert_all_backends(name, code, expected)

    def test_python_and_vm_agree_on_bench_program(self):
        """The exact program whose divergence found the two historical VM bugs."""
        code = (
            "mut total: Int = 0\n"
            "mut i: Int = 0\n"
            "while i < 1000:\n"
            "    total = total + ((i * 3 + 7) % 1000)\n"
            "    i = i + 1\n"
            "print(total)\n"
        )
        expected = str(sum((i * 3 + 7) % 1000 for i in range(1000)))
        self.assertEqual(_run_python(code), expected)
        self.assertEqual(_run_vm(code), expected)


# ─── Tier 2: known drift — tracked in issues, must shrink over time ────────
KNOWN_DRIFT = [
    # (name, code, expected, issue, backends-that-currently-diverge)
    (
        "untyped-mut",
        "mut total = 0\nmut i = 0\nwhile i < 5:\n    total += i\n    i += 1\nprint(total)",
        "10",
        23,
        ("python", "vm", "bash"),
    ),
    ("vm-fstring", 'x = 42\nprint(f"x={x}")', "x=42", 24, ("vm", "bash")),
    ("paren-print", "print((2 + 3) * 4)", "20", 25, ("bash",)),
    ("ternary-print", 'print("yes" if True else "no")', "yes", 25, ("bash",)),
    # f-string print: bash silently drops the arg (#25) AND the VM prints the
    # literal template (#24) — when either issue closes, re-triage this case.
    ("fstring-print", 'x = 42\nprint(f"x={x}")', "x=42", 25, ("vm", "bash")),
    ("call-concat", "def add(a, b):\n    return a + b\nprint(add(2, 3))", "5", 25, ("bash",)),
    ("paren-rhs-assign", "x = (7 + 8)\nprint(x)", "15", 25, ("bash",)),
    # same root cause: + on identifiers emits concat ("${a}${b}"), so the
    # return value is "23" and assignment+print propagates it
    ("function-assign", "def add(a, b):\n    return a + b\nc = add(2, 3)\nprint(c)", "5", 25, ("bash",)),
    ("bool-verbose", "print(3 < 5)", "True", 25, ("bash",)),
]


class TestKnownDrift(unittest.TestCase):
    """Known divergences: expectedFailure while the issue is open.

    When a backend gets fixed, the case XPASSes -> the grader fails ->
    promote the case to CONSENSUS_CASES. Drift only shrinks.
    """

    def _drift(self, name, code, expected, issue, expected_diverging):
        results = {}
        for backend, runner in (("python", _run_python), ("vm", _run_vm), ("bash", _run_bash)):
            try:
                results[backend] = runner(code)
            except Exception as e:
                results[backend] = f"<{backend} ERROR: {e}>"
        diverged = {b for b, o in results.items() if o != expected}
        if diverged != set(expected_diverging):
            self.fail(
                f"case '{name}' (#{issue}): drift changed! "
                f"expected diverging={sorted(expected_diverging)}, now {sorted(diverged)}. "
                f"Results: {results}. If a backend was fixed, promote this case "
                f"to CONSENSUS_CASES; if a new one drifted, triage it."
            )
        # and confirm each expected divergence actually diverges (keeps the
        # expectedFailure semantics: if nothing diverges, the test XPASSes)
        self.assertTrue(diverged, f"case '{name}' fully fixed — promote to consensus")

    def test_known_drift_cases(self):
        for name, code, expected, issue, expected_diverging in KNOWN_DRIFT:
            with self.subTest(case=name):
                # The expectedFailure applies per-case via the decorator trick:
                # run the drift assertion in a sub-test that we expect to fail
                # only when the listed backends really diverge.
                self._check(name, code, expected, issue, expected_diverging)

    def _check(self, name, code, expected, issue, expected_diverging):
        @unittest.expectedFailure
        def inner():
            self._drift(name, code, expected, issue, expected_diverging)

        inner()


if __name__ == "__main__":
    unittest.main()
