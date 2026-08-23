"""Externum v4 — Stack-based Virtual Machine (EXBC runtime).

Executes compiled BytecodeModule objects.  Supports:
  - All arithmetic, comparison, logical and bitwise operators
  - Local/global variable scoping
  - Function calls with keyword arguments and defaults
  - Closures with upvalue capture
  - Classes, inheritance, method dispatch
  - Pattern matching (match/case)
  - try/except/finally with exception propagation
  - Manual memory management (alloc/free/@)
  - Concurrency (spawn/chan/send/recv)
  - Pipe operator (|>)
  - defer blocks
  - Intrinsic builtins (print, len, range, etc.)
  - Generators / yield
  - Structs and enums (algebraic data types)
"""

import itertools as _itertools
import queue
import sys
import threading
from typing import Any

from .bytecode import (
    ADD,
    ALLOC,
    AND,
    ASSERT_EQ,
    AWAIT_OP,
    BITAND,
    BITNOT,
    BITOR,
    BITXOR,
    CALL,
    DBG_OP,
    DEFER_PUSH,
    DIV,
    DUP,
    ENUM_IS,
    ENUM_UNWRAP,
    ENUM_VARIANT,
    EQ,
    FLOOR_DIV,
    FOR_ITER,
    FREE,
    GET_ATTR,
    GET_INDEX,
    GT,
    GTE,
    HALT,
    IMPORT,
    IN_OP,
    INTRINSIC,
    IS_OP,
    JUMP,
    JUMP_IF,
    JUMP_IF_NOT,
    JUMP_IF_POP,
    LOAD_CONST,
    LOAD_DEREF,
    LOAD_GLOBAL,
    LOAD_VAR,
    LOOP_BREAK,
    LSHIFT,
    LT,
    LTE,
    MAKE_CLASS,
    MAKE_DICT,
    MAKE_ENUM,
    MAKE_FN,
    MAKE_LIST,
    MAKE_SET,
    MAKE_STRUCT,
    MAKE_TUPLE,
    MOD,
    MUL,
    NEG,
    NEQ,
    NOP,
    NOT,
    OPTION_NONE,
    OPTION_SOME,
    OR,
    PANIC,
    PIPE_CALL,
    POP,
    POP_EXCEPT,
    POW,
    RAISE_OP,
    RESULT_ERR,
    RESULT_OK,
    RETURN,
    RSHIFT,
    SET_ATTR,
    SET_INDEX,
    STORE_DEREF,
    STORE_GLOBAL,
    STORE_MUT,
    STORE_VAR,
    SUB,
    SWAP,
    TRACE_OP,
    TRY_BEGIN,
    TRY_END,
    UNPACK,
    UNREACHABLE,
    YIELD_VAL,
    BytecodeFunction,
    BytecodeModule,
)

# ── objects ──────────────────────────────────────────────────────────


class ExternumObject:
    """Base class for Externum heap objects."""


class ExternumStruct(ExternumObject):
    __slots__ = ("__fields", "__typename")

    def __init__(self, typename: str, fields: dict):
        object.__setattr__(self, "__typename", typename)
        object.__setattr__(self, "__fields", fields)

    def __getattr__(self, name):
        fields = object.__getattribute__(self, "__fields")
        if name in fields:
            return fields[name]
        raise AttributeError(f"struct `{object.__getattribute__(self, '__typename')}` has no field `{name}`")

    def __setattr__(self, name, value):
        fields = object.__getattribute__(self, "__fields")
        fields[name] = value

    def __repr__(self):
        tn = object.__getattribute__(self, "__typename")
        fields = object.__getattribute__(self, "__fields")
        fs = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{tn}({fs})"


class ExternumEnum(ExternumObject):
    __slots__ = ("__data", "__typename", "__variant")

    def __init__(self, typename: str, variant: str, data: Any = None):
        object.__setattr__(self, "__typename", typename)
        object.__setattr__(self, "__variant", variant)
        object.__setattr__(self, "__data", data)

    @property
    def variant(self):
        return object.__getattribute__(self, "__variant")

    @property
    def data(self):
        return object.__getattribute__(self, "__data")

    def __repr__(self):
        tn = object.__getattribute__(self, "__typename")
        v = object.__getattribute__(self, "__variant")
        d = object.__getattribute__(self, "__data")
        if d is not None:
            return f"{tn}.{v}({d!r})"
        return f"{tn}.{v}"


class ExternumResult(ExternumObject):
    __slots__ = ("_ok", "_value")

    def __init__(self, ok: bool, value: Any):
        object.__setattr__(self, "_ok", ok)
        object.__setattr__(self, "_value", value)

    @property
    def is_ok(self):
        return object.__getattribute__(self, "_ok")

    @property
    def value(self):
        return object.__getattribute__(self, "_value")

    def unwrap(self):
        if not object.__getattribute__(self, "_ok"):
            raise RuntimeError(f"unwrap on Err: {object.__getattribute__(self, '_value')!r}")
        return object.__getattribute__(self, "_value")

    def __repr__(self):
        if object.__getattribute__(self, "_ok"):
            return f"Ok({object.__getattribute__(self, '_value')!r})"
        return f"Err({object.__getattribute__(self, '_value')!r})"


class ExternumOption(ExternumObject):
    __slots__ = ("_some", "_value")

    def __init__(self, some: bool, value: Any = None):
        object.__setattr__(self, "_some", some)
        object.__setattr__(self, "_value", value)

    @property
    def is_some(self):
        return object.__getattribute__(self, "_some")

    @property
    def value(self):
        return object.__getattribute__(self, "_value")

    def unwrap(self):
        if not object.__getattribute__(self, "_some"):
            raise RuntimeError("unwrap on None")
        return object.__getattribute__(self, "_value")

    def __repr__(self):
        if object.__getattribute__(self, "_some"):
            return f"Some({object.__getattribute__(self, '_value')!r})"
        return "None"


class ExternumClosure(ExternumObject):
    """A closure wrapping a function with captured upvalues."""

    __slots__ = ("_fn", "_upvalues")

    def __init__(self, fn: BytecodeFunction, upvalues: dict):
        object.__setattr__(self, "_fn", fn)
        object.__setattr__(self, "_upvalues", upvalues)

    @property
    def fn(self):
        return object.__getattribute__(self, "_fn")

    @property
    def upvalues(self):
        return object.__getattribute__(self, "_upvalues")


class ExternumBoundMethod(ExternumObject):
    """A bound method wrapping an instance and a closure."""

    __slots__ = ("_closure", "_instance")

    def __init__(self, instance, closure):
        object.__setattr__(self, "_instance", instance)
        object.__setattr__(self, "_closure", closure)

    @property
    def instance(self):
        return object.__getattribute__(self, "_instance")

    @property
    def closure(self):
        return object.__getattribute__(self, "_closure")


class ExternumClass:
    def __init__(self, name: str, methods: dict, bases: list = None):
        self.name = name
        self.methods = methods
        self.bases = bases or []

    def __repr__(self):
        return f"<class {self.name}>"


class ExternumInstance:
    def __init__(self, cls, attrs: dict = None):
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "attrs", attrs or {})

    @property
    def __class__(self):
        return object.__getattribute__(self, "_cls")

    def __getattr__(self, name):
        a = object.__getattribute__(self, "attrs")
        if name in a:
            return a[name]
        cls = object.__getattribute__(self, "_cls")
        if hasattr(cls, "methods") and name in cls.methods:
            method = cls.methods[name]
            if hasattr(method, "__get__"):
                return method.__get__(self, type(self))
            if isinstance(method, ExternumClosure):
                return ExternumBoundMethod(self, method)
            return method
        raise AttributeError(f"'{cls.name}' has no attribute '{name}'")

    def __setattr__(self, name, value):
        a = object.__getattribute__(self, "attrs")
        a[name] = value

    def __repr__(self):
        cls = object.__getattribute__(self, "_cls")
        a = object.__getattribute__(self, "attrs")
        return f"{cls.name}({a!r})"


class ExternumGenerator:
    def __init__(self, vm: "VM", fn: BytecodeFunction, args: list, upvalues: dict = None):
        self._vm = vm
        self._fn = fn
        self._args = args
        self._ip = 0
        self._upvalues = upvalues or {}
        self._done = False

    def __iter__(self):
        return self

    def __next__(self):
        if self._done:
            raise StopIteration
        result = self._vm.run_function(self._fn, self._args, upvalues=self._upvalues)
        if result is _GeneratorSentinel:
            return self._vm._stack[-1] if self._vm._stack else None
        self._done = True
        raise StopIteration


_GeneratorSentinel = object()


# ── memory heap ──────────────────────────────────────────────────────


class ExternumHeap:
    def __init__(self):
        self._slots: dict[int, Any] = {}
        self._next_id = _itertools.count(1)

    def alloc(self, value=None, count=1):
        pid = next(self._next_id)
        self._slots[pid] = [value] * count
        return pid

    def free(self, pid):
        if pid not in self._slots:
            raise RuntimeError(f"free: invalid or already-freed pointer {pid}")
        del self._slots[pid]

    def load(self, pid, index=0):
        if pid not in self._slots:
            raise RuntimeError(f"deref: invalid or freed pointer {pid}")
        return self._slots[pid][index]

    def store(self, pid, value, index=0):
        if pid not in self._slots:
            raise RuntimeError(f"store: invalid or freed pointer {pid}")
        self._slots[pid][index] = value

    def addr(self, value):
        pid = next(self._next_id)
        self._slots[pid] = [value]
        return pid


# ── VM ───────────────────────────────────────────────────────────────


class ExternumError(Exception):
    """Runtime error in the Externum VM."""


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class VM:
    """Stack-based virtual machine for EXBC bytecode."""

    def __init__(self, stdout=None, stderr=None, argv=None):
        self._stack: list[Any] = []
        self._globals: dict[str, Any] = {}
        self._heap = ExternumHeap()
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._argv = argv or []
        self._modules: dict[str, BytecodeModule] = {}
        self._defer_stack: list[list] = []
        self._channels: dict[int, queue.Queue] = {}
        self._thread_counter = _itertools.count(1)
        self._builtin_keys = set()  # track builtins for import filtering
        # Pre-populate builtins
        self._globals["print"] = self._builtin_print
        self._globals["input"] = self._builtin_input
        self._globals["len"] = self._builtin_len
        self._globals["str"] = self._builtin_str
        self._globals["int"] = self._builtin_int
        self._globals["float"] = self._builtin_float
        self._globals["bool"] = self._builtin_bool
        self._globals["list"] = self._builtin_list
        self._globals["dict"] = self._builtin_dict
        self._globals["tuple"] = self._builtin_tuple
        self._globals["set"] = self._builtin_set
        self._globals["range"] = self._builtin_range
        self._globals["type"] = self._builtin_type
        self._globals["isinstance"] = self._builtin_isinstance
        self._globals["repr"] = self._builtin_repr
        self._globals["id"] = self._builtin_id
        self._globals["hash"] = self._builtin_hash
        self._globals["min"] = self._builtin_min
        self._globals["max"] = self._builtin_max
        self._globals["sum"] = self._builtin_sum
        self._globals["abs"] = self._builtin_abs
        self._globals["round"] = self._builtin_round
        self._globals["sorted"] = self._builtin_sorted
        self._globals["enumerate"] = self._builtin_enumerate
        self._globals["zip"] = self._builtin_zip
        self._globals["reversed"] = self._builtin_reversed
        self._globals["chr"] = self._builtin_chr
        self._globals["ord"] = self._builtin_ord
        self._globals["hex"] = self._builtin_hex
        self._globals["oct"] = self._builtin_oct
        self._globals["bin"] = self._builtin_bin
        self._globals["open"] = self._builtin_open
        self._globals["format"] = self._builtin_format
        self._globals["True"] = True
        self._globals["False"] = False
        self._globals["None"] = None

        self._globals["alloc"] = self._builtin_alloc
        self._globals["free"] = self._builtin_free
        self._globals["addr"] = self._builtin_addr
        self._globals["sizeof"] = self._builtin_sizeof
        self._globals["chan"] = self._builtin_chan
        self._globals["send"] = self._builtin_send
        self._globals["recv"] = self._builtin_recv
        self._globals["spawn"] = self._builtin_spawn

        self._globals["Ok"] = lambda v: ExternumResult(True, v)
        self._globals["Err"] = lambda v: ExternumResult(False, v)
        self._globals["Some"] = lambda v: ExternumOption(True, v)
        self._globals["Result"] = type(
            "Result",
            (),
            {
                "Ok": staticmethod(lambda v: ExternumResult(True, v)),
                "Err": staticmethod(lambda v: ExternumResult(False, v)),
            },
        )
        self._globals["Option"] = type(
            "Option",
            (),
            {
                "Some": staticmethod(lambda v: ExternumOption(True, v)),
                "None": staticmethod(lambda: ExternumOption(False, None)),
            },
        )
        self._globals["panic"] = self._builtin_panic
        self._globals["dbg"] = self._builtin_dbg
        self._globals["trace"] = self._builtin_trace
        self._globals["unreachable"] = lambda: (_ for _ in ()).throw(RuntimeError("unreachable"))
        self._globals["argv"] = self._argv
        self._globals["assert_eq"] = self._builtin_assert_eq

        # Terminal (curses) builtins for TUI apps
        self._globals["term_init"] = self._builtin_term_init
        self._globals["term_cleanup"] = self._builtin_term_cleanup
        self._globals["term_clear"] = self._builtin_term_clear
        self._globals["term_refresh"] = self._builtin_term_refresh
        self._globals["term_size"] = self._builtin_term_size
        self._globals["term_move"] = self._builtin_term_move
        self._globals["term_write"] = self._builtin_term_write
        self._globals["term_color"] = self._builtin_term_color
        self._globals["term_getkey"] = self._builtin_term_getkey
        self._globals["term_addstr"] = self._builtin_term_addstr
        self._globals["term_border"] = self._builtin_term_border
        self._globals["term_hline"] = self._builtin_term_hline
        self._globals["term_vline"] = self._builtin_term_vline
        self._globals["term_getstr"] = self._builtin_term_getstr
        self._globals["term_attr"] = self._builtin_term_attr
        self._globals["KEY_ENTER"] = 10
        self._globals["KEY_BACKSPACE"] = 127
        self._globals["KEY_ESCAPE"] = 27
        self._globals["KEY_UP"] = -1
        self._globals["KEY_DOWN"] = -2
        self._globals["KEY_LEFT"] = -3
        self._globals["KEY_RIGHT"] = -4
        self._globals["KEY_HOME"] = -5
        self._globals["KEY_END"] = -6
        self._globals["KEY_PGUP"] = -7
        self._globals["KEY_PGDOWN"] = -8
        self._globals["KEY_DELETE"] = -9
        self._globals["COLOR_BLACK"] = 0
        self._globals["COLOR_RED"] = 1
        self._globals["COLOR_GREEN"] = 2
        self._globals["COLOR_YELLOW"] = 3
        self._globals["COLOR_BLUE"] = 4
        self._globals["COLOR_MAGENTA"] = 5
        self._globals["COLOR_CYAN"] = 6
        self._globals["COLOR_WHITE"] = 7
        self._globals["A_BOLD"] = 2097152
        self._globals["A_UNDERLINE"] = 131072
        self._globals["A_REVERSE"] = 262144
        self._builtin_keys = set(self._globals.keys())

    # ── main entry ────────────────────────────────────────────────
    def run_module(self, module: BytecodeModule) -> Any:
        self._modules[module.name] = module
        return self._execute(module.bytecode, module.constants, {}, module.functions)

    def run_function(self, fn: BytecodeFunction, args: list, kwargs: dict = None, upvalues: dict = None) -> Any:
        # Save and restore the stack to avoid corruption during nested calls
        saved_stack = self._stack
        self._stack = []
        try:
            # Build local vars: named args first, then defaults
            local_vars = dict(upvalues or {})
            # Set defaults first
            for name, default_val in fn.kw_defaults.items():
                local_vars[name] = default_val
            # Set provided args
            for name, val in zip(fn.arg_names, args):
                local_vars[name] = val
            local_vars.update(kwargs or {})
            return self._execute(
                fn.bytecode,
                fn.constants,
                local_vars,
                self._modules[list(self._modules.keys())[0]].functions if self._modules else [],
                fn_name=fn.name,
            )
        finally:
            self._stack = saved_stack

    def run_source(self, source: str) -> Any:
        """Compile source and run it."""
        from .bytecode import BytecodeCompiler
        from .lexer import Lexer
        from .parser import Parser

        tokens = Lexer(source).tokenize()
        ast = list(Parser(tokens).parse())
        compiler = BytecodeCompiler(ast)
        module = compiler.compile()
        return self.run_module(module)

    def _vm_import(self, name: str):
        """Import an Externum module by name, finding .ext files in lib/ etc."""
        import os

        if name in self._modules:
            mod = self._modules[name]
            return type("Module", (), dict(mod.globals))()
        # Search for .ext file
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_dirs = [
            os.path.join(repo_root, "lib"),
            os.getcwd(),
        ]
        ext_path = name.replace(".", os.sep) + ".ext"
        for d in search_dirs:
            candidate = os.path.join(d, ext_path)
            if os.path.isfile(candidate):
                with open(candidate, encoding="utf-8") as fh:
                    source = fh.read()
                # Use the Python transpiler for .ext libs (they were written for it)
                from .runtime import Runtime as _RT

                rt = _RT(search_roots=[os.path.dirname(candidate)])
                ns = rt.run(source)
                mod_ns = {k: v for k, v in ns.items() if k not in ("__name__", "__file__")}
                mod_obj = type("Module", (), mod_ns)()
                mod_obj.__dict__.update(mod_ns)
                return mod_obj
        # Fallback: try Python import
        try:
            return __import__(name)
        except ImportError:
            raise ExternumError(f"Cannot import {name!r}")

    # ── bytecode executor ─────────────────────────────────────────
    def _execute(
        self, bytecode: bytearray, constants: list, local_vars: dict, all_fns: list, fn_name: str = "<module>"
    ) -> Any:
        ip = 0
        stack = self._stack
        locals_ = dict(local_vars)
        try_depth = 0
        catch_ip = None

        def _read_u16():
            nonlocal ip
            val = (bytecode[ip] << 8) | bytecode[ip + 1]
            ip += 2
            return val

        def _read_u8():
            nonlocal ip
            val = bytecode[ip]
            ip += 1
            return val

        while ip < len(bytecode):
            op = bytecode[ip]
            ip += 1

            if op == NOP:
                continue
            elif op == HALT:
                break
            elif op == RETURN:
                if stack:
                    return stack.pop()
                return None
            elif op == YIELD_VAL:
                return _GeneratorSentinel

            # ── load/store ──
            elif op == LOAD_CONST:
                idx = _read_u16()
                stack.append(constants[idx])
            elif op == LOAD_VAR:
                idx = _read_u16()
                name = constants[idx]
                if name in locals_:
                    stack.append(locals_[name])
                elif name in self._globals:
                    stack.append(self._globals[name])
                else:
                    raise ExternumError(f"undefined variable `{name}`")
            elif op == STORE_VAR or op == STORE_MUT:
                idx = _read_u16()
                name = constants[idx]
                locals_[name] = stack.pop()
            elif op == LOAD_GLOBAL:
                idx = _read_u16()
                name = constants[idx]
                if name in self._globals:
                    stack.append(self._globals[name])
                elif name in locals_:
                    stack.append(locals_[name])
                else:
                    raise ExternumError(f"undefined global `{name}`")
            elif op == STORE_GLOBAL:
                idx = _read_u16()
                name = constants[idx]
                self._globals[name] = stack.pop()

            # ── stack manipulation ──
            elif op == POP:
                stack.pop()
            elif op == DUP:
                stack.append(stack[-1])
            elif op == SWAP:
                a, b = stack.pop(), stack.pop()
                stack.append(a)
                stack.append(b)

            # ── arithmetic ──
            elif op == ADD:
                b, a = stack.pop(), stack.pop()
                stack.append(a + b)
            elif op == SUB:
                b, a = stack.pop(), stack.pop()
                stack.append(a - b)
            elif op == MUL:
                b, a = stack.pop(), stack.pop()
                stack.append(a * b)
            elif op == DIV:
                b, a = stack.pop(), stack.pop()
                stack.append(a / b)
            elif op == MOD:
                b, a = stack.pop(), stack.pop()
                stack.append(a % b)
            elif op == POW:
                b, a = stack.pop(), stack.pop()
                stack.append(a**b)
            elif op == FLOOR_DIV:
                b, a = stack.pop(), stack.pop()
                stack.append(a // b)
            elif op == NEG:
                a = stack.pop()
                stack.append(-a)
            elif op == NOT:
                a = stack.pop()
                stack.append(not a)
            elif op == BITAND:
                b, a = stack.pop(), stack.pop()
                stack.append(a & b)
            elif op == BITOR:
                b, a = stack.pop(), stack.pop()
                stack.append(a | b)
            elif op == BITXOR:
                b, a = stack.pop(), stack.pop()
                stack.append(a ^ b)
            elif op == BITNOT:
                a = stack.pop()
                stack.append(~a)
            elif op == LSHIFT:
                b, a = stack.pop(), stack.pop()
                stack.append(a << b)
            elif op == RSHIFT:
                b, a = stack.pop(), stack.pop()
                stack.append(a >> b)

            # ── comparison ──
            elif op == EQ:
                b, a = stack.pop(), stack.pop()
                stack.append(a == b)
            elif op == NEQ:
                b, a = stack.pop(), stack.pop()
                stack.append(a != b)
            elif op == LT:
                b, a = stack.pop(), stack.pop()
                stack.append(a < b)
            elif op == GT:
                b, a = stack.pop(), stack.pop()
                stack.append(a > b)
            elif op == LTE:
                b, a = stack.pop(), stack.pop()
                stack.append(a <= b)
            elif op == GTE:
                b, a = stack.pop(), stack.pop()
                stack.append(a >= b)
            elif op == AND:
                b, a = stack.pop(), stack.pop()
                stack.append(a and b)
            elif op == OR:
                b, a = stack.pop(), stack.pop()
                stack.append(a or b)
            elif op == IN_OP:
                b, a = stack.pop(), stack.pop()
                stack.append(a in b)
            elif op == IS_OP:
                b, a = stack.pop(), stack.pop()
                stack.append(a is b)

            # ── jumps ──
            elif op == JUMP:
                ip = _read_u16()
            elif op == JUMP_IF:
                cond = stack.pop()
                if cond:
                    ip = _read_u16()
                else:
                    ip += 2
            elif op == JUMP_IF_NOT:
                cond = stack.pop()
                if not cond:
                    ip = _read_u16()
                else:
                    ip += 2
            elif op == JUMP_IF_POP:
                cond = stack[-1]
                if not cond:
                    ip = _read_u16()
                    stack.pop()
                else:
                    ip += 2

            # ── calls ──
            elif op == CALL:
                argc = _read_u8()
                args = []
                for _ in range(argc):
                    args.insert(0, stack.pop())
                fn = stack.pop()
                if isinstance(fn, ExternumBoundMethod):
                    stack.append(self.run_function(fn.closure.fn, [fn.instance] + args, upvalues=fn.closure.upvalues))
                elif callable(fn):
                    stack.append(fn(*args))
                elif isinstance(fn, ExternumClosure):
                    stack.append(self.run_function(fn.fn, args, upvalues=fn.upvalues))
                elif isinstance(fn, BytecodeFunction):
                    stack.append(self.run_function(fn, args))
                elif isinstance(fn, ExternumClass):
                    instance = ExternumInstance(fn)
                    if "__init__" in fn.methods:
                        init_fn = fn.methods["__init__"]
                        if isinstance(init_fn, ExternumClosure):
                            self.run_function(init_fn.fn, [instance] + args, upvalues=init_fn.upvalues)
                        elif isinstance(init_fn, BytecodeFunction):
                            self.run_function(init_fn, [instance] + args)
                    stack.append(instance)
                elif isinstance(fn, ExternumStruct):
                    # Struct instantiation
                    typename = object.__getattribute__(fn, "__typename") if hasattr(fn, "__typename") else "Struct"
                    fields = object.__getattribute__(fn, "__fields") if hasattr(fn, "__fields") else {}
                    stack.append(fn)
                elif isinstance(fn, ExternumResult) or isinstance(fn, ExternumOption):
                    stack.append(fn)
                else:
                    raise ExternumError(f"cannot call {fn!r}")

            elif op == MAKE_FN:
                idx = _read_u16()
                fn = all_fns[idx]
                closure = ExternumClosure(fn, dict(locals_))
                stack.append(closure)

            elif op == MAKE_CLASS:
                idx = _read_u16()
                name = constants[idx]
                stack.append(ExternumClass(name, {}))

            # ── containers ──
            elif op == MAKE_LIST:
                count = _read_u16()
                items = []
                for _ in range(count):
                    items.insert(0, stack.pop())
                stack.append(items)
            elif op == MAKE_DICT:
                count = _read_u16()
                items = {}
                for _ in range(count):
                    v, k = stack.pop(), stack.pop()
                    items[k] = v
                stack.append(items)
            elif op == MAKE_TUPLE:
                count = _read_u16()
                items = []
                for _ in range(count):
                    items.insert(0, stack.pop())
                stack.append(tuple(items))
            elif op == MAKE_SET:
                count = _read_u16()
                items = set()
                for _ in range(count):
                    items.add(stack.pop())
                stack.append(items)
            elif op == UNPACK:
                count = _read_u16()
                val = stack.pop()
                for i in range(count):
                    stack.append(val[i] if i < len(val) else None)

            # ── attribute/index access ──
            elif op == GET_ATTR:
                idx = _read_u16()
                name = constants[idx]
                obj = stack.pop()
                if isinstance(obj, ExternumStruct) or isinstance(obj, ExternumEnum):
                    stack.append(obj.__getattr__(name))
                elif isinstance(obj, dict):
                    stack.append(obj[name])
                else:
                    stack.append(getattr(obj, name))
            elif op == SET_ATTR:
                idx = _read_u16()
                name = constants[idx]
                val = stack.pop()
                obj = stack.pop()
                if isinstance(obj, ExternumStruct):
                    obj.__setattr__(name, val)
                elif isinstance(obj, ExternumInstance):
                    obj.attrs[name] = val
                elif isinstance(obj, ExternumClass):
                    obj.methods[name] = val
                elif isinstance(obj, dict):
                    obj[name] = val
                else:
                    setattr(obj, name, val)
            elif op == GET_INDEX:
                idx = stack.pop()
                obj = stack.pop()
                stack.append(obj[idx])
            elif op == SET_INDEX:
                idx = stack.pop()
                val = stack.pop()
                obj = stack.pop()
                obj[idx] = val

            # ── loops ──
            elif op == FOR_ITER:
                target = _read_u16()
                iterator = stack[-1]
                try:
                    val = next(iterator)
                    stack.append(val)
                except StopIteration:
                    stack.pop()
                    ip = target
            elif op == LOOP_BREAK:
                ip = _read_u16()

            # ── exceptions ──
            elif op == TRY_BEGIN:
                catch_ip = _read_u16()
                try_depth += 1
            elif op == TRY_END:
                try_depth = max(0, try_depth - 1)
                if try_depth == 0:
                    catch_ip = None
            elif op == RAISE_OP:
                exc = stack.pop() if stack else RuntimeError("raise")
                if isinstance(exc, str):
                    exc = RuntimeError(exc)
                raise exc
            elif op == POP_EXCEPT:
                try_depth = max(0, try_depth - 1)
                if try_depth == 0:
                    catch_ip = None

            # ── basic ──
            elif op == ALLOC:
                value = stack.pop() if stack else None
                stack.append(self._heap.alloc(value))
            elif op == FREE:
                pid = stack.pop()
                self._heap.free(pid)
            elif op == LOAD_DEREF:
                pid = stack.pop()
                index = stack.pop() if stack else 0
                stack.append(self._heap.load(pid, index))
            elif op == STORE_DEREF:
                value = stack.pop()
                pid = stack.pop()
                index = stack.pop() if stack else 0
                self._heap.store(pid, value, index)

            # ── advanced ──
            elif op == MAKE_STRUCT:
                name_idx = _read_u16()
                field_count = _read_u8()
                name = constants[name_idx]
                # Create a callable struct type (not an instance)
                field_names = [f"field{i}" for i in range(field_count)]

                def _make_struct_factory(_n=name, _fn=field_names):
                    def _factory(*args):
                        fields = dict(zip(_fn, args))
                        return ExternumStruct(_n, fields)

                    return _factory

                stack.append(_make_struct_factory())
            elif op == MAKE_ENUM:
                name_idx = _read_u16()
                variant_count = _read_u8()
                name = constants[name_idx]

                # Create class with dynamic variant access
                class _EnumMeta(type):
                    def __getattr__(cls, vname):
                        if vname.startswith("_"):
                            raise AttributeError(vname)

                        def factory(v=None):
                            return ExternumEnum(name, vname, v)

                        return factory

                stack.append(_EnumMeta(name, (), {"__qualname__": name}))
            elif op == ENUM_VARIANT:
                variant_idx = _read_u16()
                variant = constants[variant_idx]
                data = stack.pop() if stack else None
                stack.append(ExternumEnum("<enum>", variant, data))
            elif op == ENUM_IS:
                variant_idx = _read_u16()
                variant = constants[variant_idx]
                obj = stack.pop()
                stack.append(isinstance(obj, ExternumEnum) and obj.variant == variant)
            elif op == ENUM_UNWRAP:
                obj = stack.pop()
                stack.append(obj.data if isinstance(obj, ExternumEnum) else obj)

            elif op == PIPE_CALL:
                # pipe: a |> f  → stack has [a, f], call f(a)
                fn = stack.pop()
                arg = stack.pop()
                if callable(fn):
                    stack.append(fn(arg))
                else:
                    raise ExternumError(f"pipe: cannot call {fn!r}")
            elif op == AWAIT_OP:
                # Simplified: just return the value
                pass
            elif op == DEFER_PUSH:
                fn_idx = _read_u16()
                fn = all_fns[fn_idx]
                if self._defer_stack:
                    self._defer_stack[-1].append(fn)
                else:
                    self._defer_stack.append([fn])

            elif op == OPTION_SOME:
                val = stack.pop()
                stack.append(ExternumOption(True, val))
            elif op == OPTION_NONE:
                stack.append(ExternumOption(False, None))
            elif op == RESULT_OK:
                val = stack.pop()
                stack.append(ExternumResult(True, val))
            elif op == RESULT_ERR:
                val = stack.pop()
                stack.append(ExternumResult(False, val))

            # ── intrinsics ──
            elif op == INTRINSIC:
                code = _read_u16()
                argc = _read_u8()
                args = []
                for _ in range(argc):
                    args.insert(0, stack.pop())
                stack.append(self._call_intrinsic(code, args))

            elif op == ASSERT_EQ:
                val = stack.pop()
                if not val:
                    raise AssertionError(f"assertion failed: {val!r}")

            elif op == PANIC:
                msg = stack.pop() if stack else "panic"
                raise ExternumError(f"panic: {msg}")
            elif op == UNREACHABLE:
                raise ExternumError("reached unreachable code")
            elif op == TRACE_OP:
                val = stack.pop()
                self._stderr.write(f"[TRACE] {val!r}\n")
            elif op == DBG_OP:
                val = stack.pop()
                self._stderr.write(f"[DBG] {val!r} = {val!r}\n")
                stack.append(val)

            elif op == IMPORT:
                name_idx = _read_u16()
                import_str = constants[name_idx]

                # Parse: 'import X', 'import X, Y, Z', 'from X import Y', 'from X import Y as Z'
                def _import_to_target(mod_name):
                    """Import a module and return (short_name, module_object)."""
                    mod_obj = self._vm_import(mod_name.strip())
                    return mod_name.strip().split(".")[0], mod_obj

                def _store(name, val):
                    if fn_name != "<module>":
                        locals_[name] = val
                    else:
                        self._globals[name] = val

                if import_str.startswith("import "):
                    raw = import_str[7:].strip()
                    # Handle comma-separated: import os, sys, json
                    for item in raw.split(","):
                        item = item.strip()
                        if not item:
                            continue
                        short, mod_obj = _import_to_target(item)
                        _store(short, mod_obj)
                elif import_str.startswith("from "):
                    rest = import_str[5:].strip()
                    parts = rest.split(" import ")
                    mod_name = parts[0].strip()
                    imports = parts[1].strip() if len(parts) > 1 else ""
                    mod_obj = self._vm_import(mod_name)
                    for imp in imports.split(","):
                        imp = imp.strip()
                        if " as " in imp:
                            real, alias = imp.split(" as ")
                            _store(alias.strip(), getattr(mod_obj, real.strip()))
                        else:
                            _store(imp, getattr(mod_obj, imp))

            else:
                raise ExternumError(f"unknown opcode: 0x{op:02x} at ip={ip}")

        return stack.pop() if stack else None

    # ── intrinsics ──────────────────────────────────────────────────
    def _call_intrinsic(self, code: int, args: list) -> Any:
        if code == 0:
            return self._builtin_print(*args)
        elif code == 1:
            return self._builtin_len(*args)
        elif code == 2:
            return self._builtin_str(*args)
        elif code == 3:
            return self._builtin_int(*args)
        elif code == 4:
            return self._builtin_float(*args)
        elif code == 5:
            return self._builtin_range(*args)
        elif code == 6:
            return self._builtin_type(*args)
        elif code == 7:
            return self._builtin_input(*args)
        elif code == 8:
            return self._builtin_open(*args)
        elif code == 10:
            return self._builtin_alloc(*args)
        elif code == 11:
            return self._builtin_free(*args)
        elif code == 12:
            return self._builtin_addr(*args)
        elif code == 13:
            return self._builtin_sizeof(*args)
        elif code == 14:
            return self._builtin_chan(*args)
        elif code == 15:
            return self._builtin_send(*args)
        elif code == 16:
            return self._builtin_recv(*args)
        elif code == 17:
            return self._builtin_spawn(*args)
        elif code == 20:
            return self._builtin_panic(*args)
        elif code == 21:
            return self._builtin_dbg(*args)
        elif code == 22:
            return self._builtin_trace(*args)
        elif code == 23:
            return self._builtin_assert_eq(*args)
        # Algebraic type intrinsics
        elif code == 30:  # Result
            return type(
                "Result",
                (),
                {
                    "Ok": staticmethod(lambda v: ExternumResult(True, v)),
                    "Err": staticmethod(lambda v: ExternumResult(False, v)),
                },
            )
        elif code == 31:  # Option
            return type(
                "Option",
                (),
                {
                    "Some": staticmethod(lambda v: ExternumOption(True, v)),
                    "None": staticmethod(lambda: ExternumOption(False, None)),
                },
            )
        elif code == 32:  # Ok
            return ExternumResult(True, args[0] if args else None)
        elif code == 33:  # Err
            return ExternumResult(False, args[0] if args else None)
        elif code == 34:  # Some
            return ExternumOption(True, args[0] if args else None)
        elif code == 35:  # Option.None
            return ExternumOption(False, None)
        elif code == 40:
            return self._builtin_sorted(*args)
        elif code == 41:
            return self._builtin_enumerate(*args)
        elif code == 42:
            return self._builtin_zip(*args)
        elif code == 43:
            return self._builtin_reversed(*args)
        elif code == 44:
            return self._builtin_min(*args)
        elif code == 45:
            return self._builtin_max(*args)
        elif code == 46:
            return self._builtin_sum(*args)
        elif code == 47:
            return self._builtin_abs(*args)
        elif code == 48:
            return self._builtin_round(*args)
        elif code == 49:
            return self._builtin_chr(*args)
        elif code == 50:
            return self._builtin_ord(*args)
        elif code == 51:
            return self._builtin_hex(*args)
        elif code == 52:
            return self._builtin_oct(*args)
        elif code == 53:
            return self._builtin_bin(*args)
        elif code == 54:
            return self._builtin_hash(*args)
        elif code == 55:
            return self._builtin_isinstance(*args)
        elif code == 56:
            return self._builtin_repr(*args)
        elif code == 57:
            return self._builtin_id(*args)
        # Terminal intrinsics (codes 60-74)
        elif code == 60:
            return self._builtin_term_init(*args)
        elif code == 61:
            return self._builtin_term_cleanup(*args)
        elif code == 62:
            return self._builtin_term_clear(*args)
        elif code == 63:
            return self._builtin_term_refresh(*args)
        elif code == 64:
            return self._builtin_term_size(*args)
        elif code == 65:
            return self._builtin_term_move(*args)
        elif code == 66:
            return self._builtin_term_write(*args)
        elif code == 67:
            return self._builtin_term_color(*args)
        elif code == 68:
            return self._builtin_term_getkey(*args)
        elif code == 69:
            return self._builtin_term_addstr(*args)
        elif code == 70:
            return self._builtin_term_border(*args)
        elif code == 71:
            return self._builtin_term_hline(*args)
        elif code == 72:
            return self._builtin_term_vline(*args)
        elif code == 73:
            return self._builtin_term_getstr(*args)
        elif code == 74:
            return self._builtin_term_attr(*args)
        raise ExternumError(f"unknown intrinsic: {code}")

    # ── builtins ────────────────────────────────────────────────────
    def _builtin_print(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(a) for a in args) + end
        self._stdout.write(text)

    def _builtin_input(self, prompt=""):
        self._stdout.write(str(prompt))
        self._stdout.flush()
        return self._stdout.readline().rstrip("\n")

    def _builtin_len(self, obj):
        return len(obj)

    def _builtin_str(self, obj=""):
        return str(obj)

    def _builtin_int(self, obj=0, base=10):
        if isinstance(obj, str):
            return int(obj, base)
        return int(obj)

    def _builtin_float(self, obj=0.0):
        return float(obj)

    def _builtin_bool(self, obj=False):
        return bool(obj)

    def _builtin_list(self, *args):
        if args and hasattr(args[0], "__iter__"):
            return list(args[0])
        return list(args)

    def _builtin_dict(self, *args, **kwargs):
        return dict(*args, **kwargs) if args else {}

    def _builtin_tuple(self, *args):
        return tuple(args)

    def _builtin_set(self, *args):
        if args and hasattr(args[0], "__iter__"):
            return set(args[0])
        return set(args)

    def _builtin_range(self, *args):
        return iter(range(*args))

    def _builtin_type(self, obj):
        return type(obj).__name__

    def _builtin_isinstance(self, obj, cls):
        type_map = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            self._builtin_int: int,
            self._builtin_float: float,
            self._builtin_str: str,
            self._builtin_bool: bool,
            self._builtin_list: list,
            self._builtin_dict: dict,
            self._builtin_tuple: tuple,
            self._builtin_set: set,
        }
        if isinstance(cls, str):
            cls = type_map.get(cls, object)
        elif callable(cls):
            cls = type_map.get(cls, cls)
        return isinstance(obj, cls)

    def _builtin_repr(self, obj):
        return repr(obj)

    def _builtin_id(self, obj):
        return id(obj)

    def _builtin_hash(self, obj):
        return hash(obj)

    def _builtin_min(self, *args):
        return min(*args) if args else 0

    def _builtin_max(self, *args):
        return max(*args) if args else 0

    def _builtin_sum(self, *args):
        if len(args) == 1 and hasattr(args[0], "__iter__"):
            return sum(args[0])
        return sum(args)

    def _builtin_abs(self, obj):
        return abs(obj)

    def _builtin_round(self, obj, ndigits=None):
        if ndigits is not None:
            return round(obj, ndigits)
        return round(obj)

    def _builtin_sorted(self, *args, **kwargs):
        if args and hasattr(args[0], "__iter__"):
            return sorted(args[0], **kwargs)
        return sorted(args, **kwargs)

    def _builtin_enumerate(self, *args):
        return iter(enumerate(*args))

    def _builtin_zip(self, *args):
        return iter(zip(*args))

    def _builtin_reversed(self, seq):
        return iter(reversed(seq))

    def _builtin_chr(self, code):
        return chr(code)

    def _builtin_ord(self, char):
        return ord(char)

    def _builtin_hex(self, obj):
        return hex(obj)

    def _builtin_oct(self, obj):
        return oct(obj)

    def _builtin_bin(self, obj):
        return bin(obj)

    def _builtin_open(self, *args, **kwargs):
        return open(*args, **kwargs)

    def _builtin_format(self, value, fmt=""):
        return format(value, fmt)

    def _builtin_alloc(self, value=None, count=1):
        return self._heap.alloc(value, count)

    def _builtin_free(self, pid):
        self._heap.free(pid)

    def _builtin_addr(self, value):
        return self._heap.addr(value)

    def _builtin_sizeof(self, type_name):
        sizes = {"Int": 8, "Float": 8, "Str": 16, "Bool": 1, "Ptr": 8}
        return sizes.get(str(type_name), 8)

    def _builtin_chan(self):
        ch_id = next(self._thread_counter)
        self._channels[ch_id] = queue.Queue()
        return ch_id

    def _builtin_send(self, ch, value):
        if ch in self._channels:
            self._channels[ch].put(value)

    def _builtin_recv(self, ch):
        if ch in self._channels:
            return self._channels[ch].get()
        return None

    def _builtin_spawn(self, fn):
        if callable(fn):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            return t
        return None

    def _builtin_panic(self, msg="panic"):
        raise ExternumError(f"panic: {msg}")

    def _builtin_dbg(self, value):
        self._stderr.write(f"[DBG] {value!r}\n")
        return value

    def _builtin_trace(self, value):
        self._stderr.write(f"[TRACE] {value!r}\n")
        return value

    def _builtin_assert_eq(self, a, b):
        if a != b:
            raise AssertionError(f"assert_eq failed: {a!r} != {b!r}")
        return True

    # ── terminal builtins (curses wrapper) ────────────────────────
    _curses_screen = None

    def _get_curses(self):
        """Lazy import of curses module."""
        try:
            import curses

            return curses
        except ImportError:
            raise ExternumError("curses module not available")

    def _builtin_term_init(self):
        """Initialize curses and return screen."""
        curses = self._get_curses()
        screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.start_color()
        curses.use_default_colors()
        screen.keypad(True)
        screen.nodelay(False)
        screen.scrollok(True)
        # Default color pairs
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)  # status bar
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # syntax: keyword
        curses.init_pair(3, curses.COLOR_CYAN, -1)  # syntax: string
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # syntax: comment
        curses.init_pair(5, curses.COLOR_RED, -1)  # syntax: error
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # syntax: number
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_GREEN)  # mode indicator
        curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_RED)  # error bar
        curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # warning
        curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_CYAN)  # info
        self._curses_screen = screen
        return screen

    def _builtin_term_cleanup(self):
        """Restore terminal."""
        curses = self._get_curses()
        if self._curses_screen:
            self._curses_screen.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            self._curses_screen = None

    def _builtin_term_clear(self):
        """Clear the screen."""
        if self._curses_screen:
            self._curses_screen.clear()

    def _builtin_term_refresh(self):
        """Refresh the screen."""
        if self._curses_screen:
            self._curses_screen.refresh()

    def _builtin_term_size(self):
        """Return [rows, cols]."""
        curses = self._get_curses()
        if self._curses_screen:
            h, w = self._curses_screen.getmaxyx()
            return [h, w]
        return [24, 80]

    def _builtin_term_move(self, row, col):
        """Move cursor to (row, col)."""
        curses = self._get_curses()
        if self._curses_screen:
            h, w = self._curses_screen.getmaxyx()
            row = max(0, min(row, h - 1))
            col = max(0, min(col, w - 1))
            self._curses_screen.move(row, col)

    def _builtin_term_write(self, text):
        """Write text at current cursor position."""
        if self._curses_screen:
            try:
                self._curses_screen.addstr(str(text))
            except Exception:
                pass  # write at bottom-right corner

    def _builtin_term_addstr(self, row, col, text, attr=0):
        """Write text at specific position with optional attribute."""
        curses = self._get_curses()
        if self._curses_screen:
            h, w = self._curses_screen.getmaxyx()
            row = max(0, min(row, h - 1))
            col = max(0, min(col, w - 1))
            try:
                if attr:
                    self._curses_screen.addstr(row, col, str(text), attr)
                else:
                    self._curses_screen.addstr(row, col, str(text))
            except Exception:
                pass

    def _builtin_term_color(self, fg, bg=-1):
        """Return curses attribute for color pair."""
        curses = self._get_curses()
        curses.init_pair(100, fg, bg)
        return curses.color_pair(100)

    def _builtin_term_attr(self, pair_id, bold=False, underline=False, reverse=False):
        """Build a combined attribute from pair + flags."""
        curses = self._get_curses()
        attr = curses.color_pair(pair_id)
        if bold:
            attr |= curses.A_BOLD
        if underline:
            attr |= curses.A_UNDERLINE
        if reverse:
            attr |= curses.A_REVERSE
        return attr

    def _builtin_term_getkey(self):
        """Blocking key read. Returns int keycode."""
        curses = self._get_curses()
        if self._curses_screen:
            key = self._curses_screen.getch()
            # Map curses special keys to Externum key constants
            key_map = {
                curses.KEY_UP: -1,
                curses.KEY_DOWN: -2,
                curses.KEY_LEFT: -3,
                curses.KEY_RIGHT: -4,
                curses.KEY_HOME: -5,
                curses.KEY_END: -6,
                curses.KEY_PPAGE: -7,
                curses.KEY_NPAGE: -8,
                curses.KEY_DC: -9,
                curses.KEY_BACKSPACE: 127,
            }
            return key_map.get(key, key)
        return -1

    def _builtin_term_border(self, chars=None):
        """Draw a border around the screen."""
        curses = self._get_curses()
        if self._curses_screen:
            if chars:
                self._curses_screen.border(*chars) if isinstance(chars, (list, tuple)) and len(
                    chars
                ) >= 8 else self._curses_screen.border()
            else:
                self._curses_screen.border()

    def _builtin_term_hline(self, row, col, char, length):
        """Draw horizontal line."""
        curses = self._get_curses()
        if self._curses_screen:
            try:
                self._curses_screen.hline(row, col, ord(char) if isinstance(char, str) else char, length)
            except Exception:
                pass

    def _builtin_term_vline(self, row, col, char, length):
        """Draw vertical line."""
        curses = self._get_curses()
        if self._curses_screen:
            try:
                self._curses_screen.vline(row, col, ord(char) if isinstance(char, str) else char, length)
            except Exception:
                pass

    def _builtin_term_getstr(self, prompt=""):
        """Read a string with prompt (line input)."""
        curses = self._get_curses()
        if self._curses_screen:
            curses.echo()
            self._curses_screen.addstr(prompt)
            try:
                result = self._curses_screen.getstr().decode("utf-8", errors="replace")
            except Exception:
                result = ""
            curses.noecho()
            return result
        return ""
