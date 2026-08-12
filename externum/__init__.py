"""
Externum - The First LLM-Native Programming Language
======================================================
Externum v3 is a complete programming language that fuses:
- Python readability + dynamic typing
- Binary performance + SIMD vectorization
- Bash system control + process orchestration

One source compiles to Python, Bash and binary targets, or runs directly
(``externum run``), with a REPL, a module system and a standard library
written in the language itself.

Roadmap modules (llm, neural, distributed, types, spec, debug) keep their
reserved API surface below; the package stays fully importable without them.
"""

__version__ = "3.0.0"
__codename__ = "Sentient"

from .lexer import Lexer
from .parser import Parser
from .compiler import Compiler

try:
    from .runtime import Runtime
except ImportError:  # pragma: no cover
    Runtime = None


def _guarded(name):
    try:
        return __import__(f"{__name__}.{name}", fromlist=["*"])
    except ImportError:
        return None


_llm = _guarded("llm")
_neural = _guarded("neural")
_distributed = _guarded("distributed")
_types = _guarded("types")
_spec = _guarded("spec")
_debug = _guarded("debug")

LLMClient = getattr(_llm, "LLMClient", None)
PromptTemplate = getattr(_llm, "PromptTemplate", None)
FunctionSchema = getattr(_llm, "FunctionSchema", None)

Tensor = getattr(_neural, "Tensor", None)
Module = getattr(_neural, "Module", None)
Linear = getattr(_neural, "Linear", None)
Conv2d = getattr(_neural, "Conv2d", None)
Attention = getattr(_neural, "Attention", None)
Autograd = getattr(_neural, "Autograd", None)

Actor = getattr(_distributed, "Actor", None)
Cluster = getattr(_distributed, "Cluster", None)
Stream = getattr(_distributed, "Stream", None)
Channel = getattr(_distributed, "Channel", None)

Type = getattr(_types, "Type", None)
DependentType = getattr(_types, "DependentType", None)
RefinementType = getattr(_types, "RefinementType", None)
EffectType = getattr(_types, "EffectType", None)

Spec = getattr(_spec, "Spec", None)
Theorem = getattr(_spec, "Theorem", None)
Proof = getattr(_spec, "Proof", None)
Verify = getattr(_spec, "Verify", None)

TimeTravelDebugger = getattr(_debug, "TimeTravelDebugger", None)
HotReloader = getattr(_debug, "HotReloader", None)

__all__ = [
    "Lexer", "Parser", "Compiler", "Runtime",
    "LLMClient", "PromptTemplate", "FunctionSchema",
    "Tensor", "Module", "Linear", "Conv2d", "Attention", "Autograd",
    "Actor", "Cluster", "Stream", "Channel",
    "Type", "DependentType", "RefinementType", "EffectType",
    "Spec", "Theorem", "Proof", "Verify",
    "TimeTravelDebugger", "HotReloader",
]
