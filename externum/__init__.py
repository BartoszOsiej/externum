"""
Externum - The First LLM-Native Programming Language
======================================================
Externum v4 is a complete, self-hosted programming language that fuses:
- Strict static typing with algebraic data types (Result, Option, enums)
- Ownership + borrow checking (Rust-style)
- Effect tracking in types
- Generics with trait bounds
- Bytecode compiler + stack-based VM (no Python transpilation needed)
- Pipe operator, async/await, defer, comptime, macros
- Bash integration + system control

One source compiles to EXBC bytecode and runs on the Externum VM,
or can still be transpiled to Python for compatibility.
"""

__version__ = "4.0.0"
__codename__ = "Abyss"

from .lexer import Lexer
from .parser import Parser
from .compiler import Compiler
from .bytecode import BytecodeCompiler, BytecodeModule, BytecodeFunction
from .vm import VM, ExternumError, ExternumObject
from .vm import (
    ExternumStruct, ExternumEnum, ExternumResult, ExternumOption,
    ExternumClosure, ExternumClass, ExternumInstance,
)
from .typesys import TypeChecker, ExternumTypeError
from .analysis import preprocess, check, check_or_raise

try:
    from .runtime import Runtime
except ImportError:  # pragma: no cover
    Runtime = None


def _guarded(name):
    try:
        return __import__(f"{__name__}.{name}", fromlist=["*"])
    except ImportError:
        return None


__all__ = [
    # Core compiler pipeline
    "Lexer", "Parser", "Compiler",
    # v4 bytecode + VM
    "BytecodeCompiler", "BytecodeModule", "BytecodeFunction",
    "VM", "ExternumError",
    # v4 algebraic types
    "ExternumObject", "ExternumStruct", "ExternumEnum",
    "ExternumResult", "ExternumOption",
    "ExternumClosure", "ExternumClass", "ExternumInstance",
    # Type system
    "TypeChecker", "ExternumTypeError",
    # Static analysis
    "preprocess", "check", "check_or_raise",
    # Legacy runtime
    "Runtime",
]
