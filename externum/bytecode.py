"""Externum v4 — Bytecode compiler: AST → EXBC (Externum Bytecode).

EXBC is a stack-based bytecode format for the Externum VM.  Each instruction
is a 1-byte opcode followed by operand bytes depending on the instruction.

Opcodes:
  NOP=0x00, HALT=0x01, RETURN=0x02, YIELD_VAL=0x03,
  LOAD_CONST=0x10, LOAD_VAR=0x11, STORE_VAR=0x12, STORE_MUT=0x13,
  LOAD_GLOBAL=0x14, STORE_GLOBAL=0x15,
  POP=0x18, DUP=0x19, SWAP=0x1A,
  ADD=0x20, SUB=0x21, MUL=0x22, DIV=0x23, MOD=0x24, POW=0x25, FLOOR_DIV=0x26,
  NEG=0x27, NOT=0x28, BITAND=0x29, BITOR=0x2A, BITXOR=0x2B, BITNOT=0x2C,
  LSHIFT=0x2D, RSHIFT=0x2E,
  EQ=0x30, NEQ=0x31, LT=0x32, GT=0x33, LTE=0x34, GTE=0x35,
  AND=0x38, OR=0x39, IN_OP=0x3A, IS_OP=0x3B,
  JUMP=0x40, JUMP_IF=0x41, JUMP_IF_NOT=0x42, JUMP_IF_POP=0x43,
  CALL=0x50, CALL_KW=0x51, CALL_STAR=0x52, CALL_DSTAR=0x53,
  MAKE_FN=0x54, MAKE_CLASS=0x55,
  GET_ATTR=0x60, SET_ATTR=0x61, GET_INDEX=0x62, SET_INDEX=0x63,
  MAKE_LIST=0x70, MAKE_DICT=0x71, MAKE_TUPLE=0x72, MAKE_SET=0=0x73,
  UNPACK=0x74, SLICE=0x75,
  FOR_ITER=0x80, FOR_NEXT=0x81, LOOP_CONTINUE=0x82, LOOP_BREAK=0x83,
  TRY_BEGIN=0x90, TRY_END=0x91, RAISE=0x92, POP_EXCEPT=0x93,
  IMPORT=0xA0, IMPORT_FROM=0xA1, IMPORT_AS=0xA2,
  
  ALLOC=0xB0, FREE=0xB1, LOAD_DEREF=0xB2, STORE_DEREF=0xB3,
  SPAWN=0xB4, CHAN_CREATE=0xB5, CHAN_SEND=0xB6, CHAN_RECV=0xB7,
  MATCH_BEGIN=0xB8, MATCH_CASE=0xB9, MATCH_FAIL=0xBA,
  
  MAKE_STRUCT=0xC0, STRUCT_INIT=0xC1, GET_FIELD=0xC2, SET_FIELD=0xC3,
  MAKE_ENUM=0xC3, ENUM_VARIANT=0xC4, ENUM_IS=0xC5, ENUM_UNWRAP=0xC6,
  PIPE_CALL=0xC7, AWAIT_OP=0xC8, ASYNC_BEGIN=0xC9, ASYNC_END=0xCA,
  DEFER_BEGIN=0xCB, DEFER_END=0xCC,
  OPTION_SOME=0xCD, OPTION_NONE=0xCE, OPTION_UNWRAP=0xCF,
  RESULT_OK=0xD0, RESULT_ERR=0xD1, RESULT_UNWRAP=0xD2,
  COMPTIME_EVAL=0xD3, TYPE_CHECK=0xD4,
  ASSERT_EQ=0xE0, ASSERT_NE=0xE1, PANIC=0xE2, UNREACHABLE=0xE3,
  TRACE_OP=0xE4, DBG_OP=0xE5,
  MAKE_GENERATOR=0xE6, GEN_NEXT=0xE7, GEN_SEND=0xE8,
  # Intrinsics (VM-provided builtins)
  INTRINSIC=0xF0,
"""

import struct
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .parser import ASTNode

# ── opcodes ──────────────────────────────────────────────────────────
NOP = 0x00
HALT = 0x01
RETURN = 0x02
YIELD_VAL = 0x03

LOAD_CONST = 0x10
LOAD_VAR = 0x11
STORE_VAR = 0x12
STORE_MUT = 0x13
LOAD_GLOBAL = 0x14
STORE_GLOBAL = 0x15

POP = 0x18
DUP = 0x19
SWAP = 0x1A

ADD = 0x20
SUB = 0x21
MUL = 0x22
DIV = 0x23
MOD = 0x24
POW = 0x25
FLOOR_DIV = 0x26
NEG = 0x27
NOT = 0x28
BITAND = 0x29
BITOR = 0x2A
BITXOR = 0x2B
BITNOT = 0x2C
LSHIFT = 0x2D
RSHIFT = 0x2E

EQ = 0x30
NEQ = 0x31
LT = 0x32
GT = 0x33
LTE = 0x34
GTE = 0x35
AND = 0x38
OR = 0x39
IN_OP = 0x3A
IS_OP = 0x3B

JUMP = 0x40
JUMP_IF = 0x41
JUMP_IF_NOT = 0x42
JUMP_IF_POP = 0x43

CALL = 0x50
CALL_KW = 0x51
MAKE_FN = 0x54
MAKE_CLASS = 0x55

GET_ATTR = 0x60
SET_ATTR = 0x61
GET_INDEX = 0x62
SET_INDEX = 0x63

MAKE_LIST = 0x70
MAKE_DICT = 0x71
MAKE_TUPLE = 0x72
MAKE_SET = 0x73
UNPACK = 0x74
SLICE = 0x75

FOR_ITER = 0x80
LOOP_BREAK = 0x83

TRY_BEGIN = 0x90
TRY_END = 0x91
RAISE_OP = 0x92
POP_EXCEPT = 0x93

IMPORT = 0xA0

ALLOC = 0xB0
FREE = 0xB1
LOAD_DEREF = 0xB2
STORE_DEREF = 0xB3
SPAWN = 0xB4
CHAN_CREATE = 0xB5
CHAN_SEND = 0xB6
CHAN_RECV = 0xB7

MAKE_STRUCT = 0xC0
STRUCT_INIT = 0xC1
GET_FIELD = 0xC2
SET_FIELD = 0xC3
MAKE_ENUM = 0xC4
ENUM_VARIANT = 0xC5
ENUM_IS = 0xC6
ENUM_UNWRAP = 0xC7
PIPE_CALL = 0xC8
AWAIT_OP = 0xC9
DEFER_PUSH = 0xCA

OPTION_SOME = 0xD0
OPTION_NONE = 0xD1
RESULT_OK = 0xD2
RESULT_ERR = 0xD3

ASSERT_EQ = 0xE0
PANIC = 0xE2
UNREACHABLE = 0xE3
TRACE_OP = 0xE4
DBG_OP = 0xE5

INTRINSIC = 0xF0

# ── helpers ──────────────────────────────────────────────────────────

@dataclass
class BytecodeFunction:
    """A compiled function: name, bytecode, constants, inner functions."""
    name: str
    arg_names: List[str] = field(default_factory=list)
    kw_defaults: Dict[str, Any] = field(default_factory=dict)
    bytecode: bytearray = field(default_factory=bytearray)
    constants: List[Any] = field(default_factory=list)
    inner_fns: List['BytecodeFunction'] = field(default_factory=list)
    is_async: bool = False
    upvalues: List[str] = field(default_factory=list)
    line_table: Dict[int, int] = field(default_factory=dict)  # bytecode_offset -> line


@dataclass
class BytecodeModule:
    """A compiled module: top-level bytecode, constants, functions."""
    name: str
    bytecode: bytearray = field(default_factory=bytearray)
    constants: List[Any] = field(default_factory=list)
    functions: List[BytecodeFunction] = field(default_factory=list)
    structs: Dict[str, dict] = field(default_factory=dict)
    enums: Dict[str, dict] = field(default_factory=dict)
    traits: Dict[str, dict] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)


class BytecodeCompiler:
    """Compiles Externum AST → EXBC bytecode."""

    def __init__(self, ast: List[ASTNode], module_name: str = '<main>'):
        self.ast = ast
        self.module = BytecodeModule(name=module_name)
        self._current_fn: Optional[BytecodeFunction] = None
        self._scope_stack: List[Dict[str, int]] = [{}]  # name -> stack depth
        self._const_pool: List[Any] = self.module.constants
        self._loop_stack: List[List[int]] = []  # stack of (break_patches)
        self._loop_start_stack: List[int] = []  # stack of loop body start offsets
        self._defer_stack: List[List[int]] = []  # stack of defer instruction offsets
        self._try_depth = 0
        self._line = 1

    # ── public API ──────────────────────────────────────────────────
    def compile(self) -> BytecodeModule:
        for node in self.ast:
            self._compile_stmt(node)
        self._emit(HALT)
        return self.module

    # ── bytecode emission ──────────────────────────────────────────
    def _emit(self, op: int, *args: int):
        """Emit opcode + u16 operands (consistent with VM _read_u16)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        for a in args:
            target.extend(struct.pack('>H', a & 0xFFFF))
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        return offset

    def _emit1(self, op: int, byte: int):
        """Emit opcode + single u8 byte (for CALL argc, INTRINSIC argc, MAKE_STRUCT fields, etc)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.append(byte & 0xFF)
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        return offset

    def _emit2(self, op: int, idx: int, byte: int):
        """Emit opcode + u16 index + u8 count (for INTRINSIC, MAKE_STRUCT, MAKE_ENUM)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.extend(struct.pack('>H', idx & 0xFFFF))
        target.append(byte & 0xFF)
        if self._current_fn:
            self._current_fn.line_table[offset] = self._line
        return offset

    def _emit_jump(self, op: int) -> int:
        """Emit a jump instruction and return the offset of the operand (for patching)."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        offset = len(target)
        target.append(op & 0xFF)
        target.extend(b'\x00\x00')  # placeholder for u16
        return offset + 1

    def _patch_jump(self, jump_offset: int):
        """Patch a jump instruction to point to the current position."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        dest = len(target)
        target[jump_offset] = (dest >> 8) & 0xFF
        target[jump_offset + 1] = dest & 0xFF

    def _patch_jump_to(self, jump_offset: int, target_pos: int):
        """Patch a jump instruction to point to a specific position."""
        target = self._current_fn.bytecode if self._current_fn else self.module.bytecode
        target[jump_offset] = (target_pos >> 8) & 0xFF
        target[jump_offset + 1] = target_pos & 0xFF

    def _add_const(self, value: Any) -> int:
        pool = self._current_fn.constants if self._current_fn else self._const_pool
        for i, c in enumerate(pool):
            if c == value and type(c) is type(value):
                return i
        pool.append(value)
        return len(pool) - 1

    def _enter_scope(self):
        self._scope_stack.append({})

    def _exit_scope(self):
        self._scope_stack.pop()

    def _resolve(self, name: str) -> Tuple[str, int]:
        """Resolve a variable name. Returns ('local', depth) or ('global', 0)."""
        for depth in range(len(self._scope_stack) - 1, -1, -1):
            if name in self._scope_stack[depth]:
                return 'local', depth
        return 'global', 0

    def _current_depth(self) -> int:
        return len(self._scope_stack) - 1

    def _declare_var(self, name: str, depth: Optional[int] = None):
        if depth is None:
            depth = self._current_depth()
        self._scope_stack[depth][name] = len(self._scope_stack[depth])

    # ── statements ─────────────────────────────────────────────────
    def _compile_stmt(self, node: ASTNode):
        if node is None:
            return
        t = node.type
        if t == 'NEWLINE' or t in ('INDENT', 'DEDENT'):
            return
        method = getattr(self, f'_stmt_{t}', None)
        if method:
            method(node)
        elif t == 'EXPRESSION':
            self._compile_expr(node)
            self._emit(POP)
        elif t == 'CALL':
            self._compile_expr(node)
            self._emit(POP)
        elif t == 'DEL':
            if node.children:
                self._compile_expr(node.children[0])
                self._emit(POP)
        else:
            # generic: compile expression children
            for child in node.children:
                if child and hasattr(child, 'type'):
                    self._compile_stmt(child)

    def _stmt_ASSIGN(self, node: ASTNode):
        if node.value:  # tuple unpacking: "a, b = expr"
            names = [n.strip() for n in node.value.split(',') if n.strip()]
            self._compile_expr(node.children[0] if node.children else ASTNode('IDENTIFIER', value='None'))
            self._emit(UNPACK, len(names))
            for name in reversed(names):
                kind, _ = self._resolve(name)
                idx = self._add_const(name)
                if kind == 'global':
                    self._emit(STORE_GLOBAL, idx)
                else:
                    self._emit(STORE_VAR, idx)
                self._declare_var(name)
            return
        if not node.children:
            return
        target = node.children[0]
        value = node.children[1] if len(node.children) > 1 else None
        if value:
            self._compile_expr(value)
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        if target.type == 'IDENTIFIER':
            name = target.value
            kind, _ = self._resolve(name)
            idx = self._add_const(name)
            if kind == 'global' or self._current_fn is None:
                self._emit(STORE_GLOBAL, idx)
            else:
                self._emit(STORE_VAR, idx)
            self._declare_var(name)
        elif target.type == 'DOT':
            # obj.attr = val
            parts = target.value.rsplit('.', 1)
            if len(parts) == 2:
                self._compile_name(parts[0])
                # val is already on stack from above, swap
                self._emit(SWAP)
                attr_idx = self._add_const(parts[1])
                self._emit(SET_ATTR, attr_idx)
        elif target.type == 'INDEX':
            # obj[i] = val — target.value is like "x[0]"
            inner = target.value
            bracket = inner.find('[')
            if bracket > 0:
                self._compile_name(inner[:bracket])
                idx_expr = inner[bracket + 1:-1]
                self._compile_simple_expr(idx_expr)
                self._emit(SWAP)  # obj, idx, val → obj, val, idx
                # rearrange: obj, val, idx → obj, idx, val
                self._emit(SWAP)
                self._emit(SET_INDEX)
        elif target.type == 'DEREF':
            if target.children:
                self._compile_expr(target.children[0])
            self._emit(STORE_DEREF)

    def _stmt_AUG_ASSIGN(self, node: ASTNode):
        target = node.children[0] if node.children else None
        val = node.children[1] if len(node.children) > 1 else None
        op = node.children[2].value if len(node.children) > 2 else '+'
        if target and target.type == 'IDENTIFIER':
            self._compile_name(target.value)
        if val:
            self._compile_expr(val)
        op_map = {'+': ADD, '-': SUB, '*': MUL, '/': DIV, '%': MOD, '**': POW,
                  '//': FLOOR_DIV, '&': BITAND, '|': BITOR, '^': BITXOR,
                  '<<': LSHIFT, '>>': RSHIFT}
        self._emit(op_map.get(op, ADD))
        name = target.value if target and target.type == 'IDENTIFIER' else ''
        kind, _ = self._resolve(name) if name else ('global', 0)
        idx = self._add_const(name) if name else 0
        if kind == 'global':
            self._emit(STORE_GLOBAL, idx)
        else:
            self._emit(STORE_VAR, idx)

    def _stmt_FUNCTION(self, node: ASTNode):
        self._compile_function_def(node)

    def _compile_function_def(self, node: ASTNode, is_async: bool = False):
        name = node.value
        params_node = node.children[0] if node.children and node.children[0].type == 'PARAMS' else None
        body_nodes = node.children[1:] if params_node else node.children

        arg_names = []
        kw_defaults = {}
        if params_node:
            # Parse defaults from the PARAMS string value (e.g. "name='world'")
            params_str = str(params_node.value) if params_node.value else ''
            defaults = {}
            if params_str:
                for part in self._parse_list_items(params_str):
                    if '=' in part:
                        k, v = part.split('=', 1)
                        defaults[k.strip()] = self._eval_const(v.strip())
            for p in params_node.children or []:
                pname = p.value
                pname = pname.lstrip('*')
                if pname in defaults:
                    kw_defaults[pname] = defaults[pname]
                arg_names.append(pname)

        fn = BytecodeFunction(
            name=name,
            arg_names=arg_names,
            kw_defaults=kw_defaults,
            is_async=is_async,
        )
        old_fn = self._current_fn
        self._current_fn = fn
        old_scope = self._scope_stack
        self._scope_stack = [{}]
        for a in arg_names:
            self._declare_var(a)

        for child in body_nodes:
            self._compile_stmt(child)
        self._emit(RETURN)

        self._current_fn = old_fn
        self._scope_stack = old_scope

        # Emit MAKE_FN at the call site
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(MAKE_FN, fn_idx)
        name_idx = self._add_const(name)
        # At module level, store as global so recursive calls can find it
        if self._current_fn is None:
            self._emit(STORE_GLOBAL, name_idx)
        else:
            self._emit(STORE_VAR, name_idx)
        self._declare_var(name)

    def _stmt_CLASS(self, node: ASTNode):
        name = node.value
        bases = ''
        if node.children and node.children[0].type == 'PARAMS':
            bases = node.children[0].value
        body = node.children[1:] if node.children and node.children[0].type == 'PARAMS' else node.children

        # Compile each method as a function
        methods = []
        for child in body:
            if child.type == 'FUNCTION':
                self._compile_function_def(child)
                methods.append(child.value)
            elif child.type == 'ASSIGN':
                # class-level attribute assignment
                pass

        # Now create the class
        self._emit(LOAD_CONST, self._add_const(name))
        self._emit(MAKE_CLASS, self._add_const(name))

        # For each compiled method, get it from the stack and set as class attr
        # The methods were compiled as top-level functions; now attach them
        class_idx = len(self._stack_tracker) if hasattr(self, '_stack_tracker') else 0

        # Store class name
        idx = self._add_const(name)
        self._emit(STORE_VAR, idx)
        self._declare_var(name)

        # Now set each method on the class
        for mname in methods:
            self._compile_name(name)  # push class
            self._compile_name(mname)  # push method fn
            self._emit(SET_ATTR, self._add_const(mname))

    def _stmt_IF(self, node: ASTNode):
        if not node.children:
            return
        self._compile_expr(node.children[0])
        end_patches = []
        jf = self._emit_jump(JUMP_IF_NOT)
        # if body
        for child in node.children[1:]:
            if child.type in ('ELIF', 'ELSE'):
                break
            self._compile_stmt(child)
        end_patches.append(self._emit_jump(JUMP))
        self._patch_jump(jf)
        for child in node.children[1:]:
            if child.type == 'ELIF':
                self._compile_expr(child.children[0])
                jf2 = self._emit_jump(JUMP_IF_NOT)
                for sub in child.children[1:]:
                    if sub.type in ('ELIF', 'ELSE'):
                        break
                    self._compile_stmt(sub)
                end_patches.append(self._emit_jump(JUMP))
                self._patch_jump(jf2)
            elif child.type == 'ELSE':
                for sub in child.children:
                    self._compile_stmt(sub)
        for p in end_patches:
            self._patch_jump(p)

    def _stmt_FOR(self, node: ASTNode):
        var = node.value or '_'
        iterable = None
        body = list(node.children)
        if node.children and node.children[0].type == 'ITERABLE':
            iterable = node.children[0].children[0] if node.children[0].children else None
            body = node.children[1:]

        # push iterator
        if iterable:
            self._compile_expr(iterable)
        else:
            self._emit(LOAD_CONST, self._add_const(range(0)))

        loop_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        for_offset = self._emit_jump(FOR_ITER)

        # Handle tuple unpacking: for i, v in ...
        if ',' in str(var):
            names = [n.strip() for n in str(var).split(',') if n.strip()]
            # Store to temp, then unpack
            tmp = '__for_tmp__'
            tmp_idx = self._add_const(tmp)
            self._emit(STORE_VAR, tmp_idx)
            self._declare_var(tmp)
            # Load and unpack
            self._compile_name(tmp)
            self._emit(UNPACK, len(names))
            for name in reversed(names):
                self._declare_var(name)
                idx = self._add_const(name)
                self._emit(STORE_VAR, idx)
        else:
            self._declare_var(var)
            var_idx = self._add_const(var)
            self._emit(STORE_VAR, var_idx)

        self._loop_stack.append([])
        self._loop_start_stack.append(loop_start)
        for child in body:
            self._compile_stmt(child)
        # jump back
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, loop_start)

        self._patch_jump(for_offset)
        # patch breaks
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_WHILE(self, node: ASTNode):
        body_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        if node.children:
            self._compile_expr(node.children[0])
        jf = self._emit_jump(JUMP_IF_NOT)

        self._loop_stack.append([])
        self._loop_start_stack.append(body_start)
        for child in node.children[1:]:
            self._compile_stmt(child)
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, body_start)

        self._patch_jump(jf)
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_LOOP(self, node: ASTNode):
        """loop: ... break val — infinite loop with value return."""
        loop_start = len(self._current_fn.bytecode if self._current_fn else self.module.bytecode)
        self._loop_stack.append([])
        self._loop_start_stack.append(loop_start)
        for child in node.children:
            self._compile_stmt(child)
        jump_off = self._emit_jump(JUMP)
        self._patch_jump_to(jump_off, loop_start)
        self._loop_start_stack.pop()
        for bp in self._loop_stack.pop():
            self._patch_jump(bp)

    def _stmt_TRY(self, node: ASTNode):
        try_start = self._emit_jump(TRY_BEGIN)
        for child in node.children:
            if child.type not in ('EXCEPT', 'TRY_ELSE', 'FINALLY'):
                self._compile_stmt(child)
        self._emit(TRY_END)
        end_patches = [self._emit_jump(JUMP)]
        self._patch_jump(try_start)
        for child in node.children:
            if child.type == 'EXCEPT':
                # except Type as e: body
                for sub in child.children:
                    if sub.type == 'AS_VAR':
                        self._declare_var(sub.value)
                for sub in child.children:
                    if sub.type not in ('COND', 'AS_VAR'):
                        self._compile_stmt(sub)
                self._emit(POP_EXCEPT)
        for p in end_patches:
            self._patch_jump(p)

    def _stmt_RETURN(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        self._emit(RETURN)

    def _stmt_BREAK(self, node: ASTNode):
        jf = self._emit_jump(LOOP_BREAK)
        if self._loop_stack:
            self._loop_stack[-1].append(jf)

    def _stmt_CONTINUE(self, node: ASTNode):
        if self._loop_start_stack:
            jf = self._emit_jump(JUMP)
            self._patch_jump_to(jf, self._loop_start_stack[-1])

    def _stmt_PASS(self, node: ASTNode):
        self._emit(NOP)

    def _stmt_IMPORT(self, node: ASTNode):
        idx = self._add_const(node.value)
        self._emit(IMPORT, idx)

    def _stmt_RAISE(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(RAISE_OP)

    def _stmt_ASSERT(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
            self._emit(ASSERT_EQ)  # simplified: just assert truthiness

    def _stmt_TRAIT(self, node: ASTNode):
        name = node.value
        methods = []
        for child in node.children:
            if child.type == 'FUNCTION':
                methods.append(child.value)
        self.module.traits[name] = {'methods': methods}

    def _stmt_IMPL(self, node: ASTNode):
        # Store impl metadata — runtime handles dispatch
        pass

    def _stmt_MATCH(self, node: ASTNode):
        """match expr: case pattern: body — compiled as if/elif chain."""
        if not node.children:
            return
        self._compile_expr(node.children[0])
        subject_name = '__match_subject__'
        idx = self._add_const(subject_name)
        self._emit(STORE_VAR, idx)
        self._declare_var(subject_name)

        end_patches = []
        for child in node.children[1:]:
            if child.type == 'CASE':
                self._compile_name(subject_name)
                pat = child.children[0].value if child.children else '_'
                if pat == '_':
                    # wildcard — always matches
                    self._emit(POP)
                    for sub in child.children[1:]:
                        if sub.type != 'GUARD':
                            self._compile_stmt(sub)
                    end_patches.append(self._emit_jump(JUMP))
                else:
                    # Try to convert numeric patterns to actual numbers
                    pat_val = pat
                    try:
                        pat_val = int(pat)
                    except (ValueError, TypeError):
                        try:
                            pat_val = float(pat)
                        except (ValueError, TypeError):
                            pass
                    pat_idx = self._add_const(pat_val)
                    self._emit(LOAD_CONST, pat_idx)
                    self._emit(EQ)
                    jf = self._emit_jump(JUMP_IF_NOT)
                    for sub in child.children[1:]:
                        if sub.type != 'GUARD':
                            self._compile_stmt(sub)
                    end_patches.append(self._emit_jump(JUMP))
                    self._patch_jump(jf)
        for p in end_patches:
            self._patch_jump(p)

    def _stmt_STRUCT(self, node: ASTNode):
        name = node.value
        fields = []
        for child in node.children:
            if hasattr(child, 'value'):
                fields.append(child.value.split(':')[0].strip() if ':' in str(child.value) else str(child.value))
        self.module.structs[name] = {'fields': fields}
        # Emit MAKE_STRUCT
        self._emit2(MAKE_STRUCT, self._add_const(name), len(fields))
        idx = self._add_const(name)
        self._emit(STORE_VAR, idx)
        self._declare_var(name)

    def _stmt_ENUM(self, node: ASTNode):
        name = node.value
        variants = {}
        for child in node.children:
            vname = child.value if hasattr(child, 'value') else 'Unknown'
            variants[vname] = []
        self.module.enums[name] = {'variants': variants}
        self._emit2(MAKE_ENUM, self._add_const(name), len(variants))
        idx = self._add_const(name)
        if self._current_fn is None:
            self._emit(STORE_GLOBAL, idx)
        else:
            self._emit(STORE_VAR, idx)
        self._declare_var(name)

    def _stmt_CONST(self, node: ASTNode):
        if node.children and len(node.children) >= 1:
            name = node.value
            self._compile_expr(node.children[0])
            idx = self._add_const(name)
            if self._current_fn is None:
                self._emit(STORE_GLOBAL, idx)
            else:
                self._emit(STORE_VAR, idx)
            self._declare_var(name)

    def _stmt_STATIC(self, node: ASTNode):
        self._stmt_CONST(node)  # similar semantics in bytecode

    def _stmt_DEFER(self, node: ASTNode):
        """defer: body — push deferred expressions."""
        # In bytecode we store the function index for deferred code
        fn = BytecodeFunction(name='<defer>', arg_names=[])
        old_fn = self._current_fn
        self._current_fn = fn
        for child in node.children:
            self._compile_stmt(child)
        self._emit(RETURN)
        self._current_fn = old_fn
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(DEFER_PUSH, fn_idx)

    def _stmt_YIELD(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(YIELD_VAL)

    def _stmt_WITH(self, node: ASTNode):
        """with expr as var: body — simplified to try/finally."""
        if node.children:
            for child in node.children:
                self._compile_stmt(child)

    def _stmt_GLOBAL(self, node: ASTNode):
        pass  # already handled by scope resolution

    def _stmt_NONLOCAL(self, node: ASTNode):
        pass

    # ── expressions ────────────────────────────────────────────────
    def _compile_expr(self, node: ASTNode):
        if node is None:
            self._emit(LOAD_CONST, self._add_const(None))
            return
        t = node.type
        method = getattr(self, f'_expr_{t}', None)
        if method:
            method(node)
        else:
            # fallback for string-rendered expressions
            self._compile_simple_expr(str(node.value) if node.value else 'None')

    def _expr_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_BINARY_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_OCTAL_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_HEX_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_HEX_NUMBER(self, node: ASTNode):
        self._emit(LOAD_CONST, self._add_const(node.value))

    def _expr_CHAR(self, node: ASTNode):
        val = node.value
        if len(val) == 3 and val[0] == "'" and val[-1] == "'":
            val = val[1:-1]
            if val.startswith('\\'):
                escape_map = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '\\': '\\', "'": "'"}
                val = escape_map.get(val[1], val[1])
        self._emit(LOAD_CONST, self._add_const(val))

    def _expr_STRING(self, node: ASTNode):
        val = node.value
        if isinstance(val, str) and len(val) >= 2:
            if val[0] in 'fFrRbBuU' and val[1] in ('"', "'"):
                val = val[1:]  # strip prefix
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
        self._emit(LOAD_CONST, self._add_const(val))

    def _expr_IDENTIFIER(self, node: ASTNode):
        name = node.value
        if name in ('True',):
            self._emit(LOAD_CONST, self._add_const(True))
            return
        if name in ('False',):
            self._emit(LOAD_CONST, self._add_const(False))
            return
        if name in ('None',):
            self._emit(LOAD_CONST, self._add_const(None))
            return
        self._compile_name(name)

    def _expr_EXPRESSION(self, node: ASTNode):
        self._compile_simple_expr(str(node.value))

    def _expr_BINOP(self, node: ASTNode):
        op_node = node.children[1] if len(node.children) > 1 else None
        op = op_node.value if op_node else '+'
        if op == 'if_else':
            self._compile_expr(node.children[0])
            jfalse = self._emit_jump(JUMP_IF_NOT)
            self._compile_expr(node.children[2])
            end = self._emit_jump(JUMP)
            self._patch_jump(jfalse)
            self._compile_expr(node.children[3])
            self._patch_jump(end)
            return
        self._compile_expr(node.children[0])
        self._compile_expr(node.children[2])
        op_map = {
            '+': ADD, '-': SUB, '*': MUL, '/': DIV, '%': MOD,
            '**': POW, '//': FLOOR_DIV,
            '&': BITAND, '|': BITOR, '^': BITXOR,
            '<<': LSHIFT, '>>': RSHIFT,
            '==': EQ, '!=': NEQ, '<': LT, '>': GT, '<=': LTE, '>=': GTE,
            'and': AND, 'or': OR, 'in': IN_OP, 'is': IS_OP,
            'is not': IS_OP,
        }
        self._emit(op_map.get(op, ADD))

    def _expr_UNARYOP(self, node: ASTNode):
        op_node = node.children[0] if node.children else None
        op = op_node.value if op_node else '-'
        operand = node.children[1] if len(node.children) > 1 else None
        self._compile_expr(operand)
        if op == 'not':
            self._emit(NOT)
        elif op == '-':
            self._emit(NEG)
        elif op == '+':
            pass
        elif op == '~':
            self._emit(BITNOT)

    def _expr_CALL(self, node: ASTNode):
        fn = node.value
        # Built-in calls
        builtin_map = {
            'print': 0, 'len': 1, 'str': 2, 'int': 3, 'float': 4,
            'range': 5, 'type': 6, 'input': 7, 'open': 8,
            'alloc': 10, 'free': 11, 'addr': 12, 'sizeof': 13,
            'chan': 14, 'send': 15, 'recv': 16, 'spawn': 17,
            'panic': 20, 'dbg': 21, 'trace': 22,
            'assert_eq': 23, 'unreachable': 24,
            'Result': 30, 'Option': 31, 'Ok': 32, 'Err': 33,
            'Some': 34, 'Option.None': 35,
            'sorted': 40, 'enumerate': 41, 'zip': 42,
            'reversed': 43, 'min': 44, 'max': 45, 'sum': 46,
            'abs': 47, 'round': 48, 'chr': 49, 'ord': 50,
            'hex': 51, 'oct': 52, 'bin': 53, 'hash': 54,
            'isinstance': 55, 'repr': 56, 'id': 57,
            # Terminal builtins
            'term_init': 60, 'term_cleanup': 61, 'term_clear': 62,
            'term_refresh': 63, 'term_size': 64, 'term_move': 65,
            'term_write': 66, 'term_color': 67, 'term_getkey': 68,
            'term_addstr': 69, 'term_border': 70, 'term_hline': 71,
            'term_vline': 72, 'term_getstr': 73, 'term_attr': 74,
        }
        if fn in builtin_map:
            # INTRINSIC: args pushed first, then opcode handles them
            for child in node.children:
                self._compile_expr(child)
            self._emit2(INTRINSIC, builtin_map[fn], len(node.children))
        else:
            # User function: push fn first, then args (VM pops args then fn)
            # Handle dotted names like g.greet, Color.Red, o.unwrap
            if '.' in fn:
                parts = fn.rsplit('.', 1)
                self._compile_name(parts[0])  # push obj
                self._emit(GET_ATTR, self._add_const(parts[1]))  # pop obj, push bound method
                for child in node.children:
                    self._compile_expr(child)
                self._emit1(CALL, len(node.children))
            else:
                self._compile_name(fn)
                for child in node.children:
                    self._compile_expr(child)
                self._emit1(CALL, len(node.children))

    def _expr_LIST(self, node: ASTNode):
        val = node.value
        if val == '[]':
            self._emit(MAKE_LIST, 0)
            return
        # Parse items from string
        items = self._parse_list_items(val[1:-1]) if val.startswith('[') else []
        for item in items:
            self._compile_simple_expr(item.strip())
        self._emit(MAKE_LIST, len(items))

    def _expr_DICT(self, node: ASTNode):
        val = node.value
        if val == '{}':
            self._emit(MAKE_DICT, 0)
            return
        # Parse key-value pairs from string like '{"a": 1, "b": 2}'
        inner = val[1:-1].strip() if val.startswith('{') and val.endswith('}') else val
        if not inner:
            self._emit(MAKE_DICT, 0)
            return
        pairs = self._parse_list_items(inner)
        for pair in pairs:
            if ':' in pair:
                k, v = pair.split(':', 1)
                self._compile_simple_expr(k.strip())
                self._compile_simple_expr(v.strip())
            else:
                self._compile_simple_expr(pair.strip())
                self._emit(LOAD_CONST, self._add_const(None))
        self._emit(MAKE_DICT, len(pairs))

    def _expr_SET(self, node: ASTNode):
        val = node.value
        items = self._parse_list_items(val[1:-1]) if val.startswith('{') else []
        for item in items:
            self._compile_simple_expr(item.strip())
        self._emit(MAKE_SET, len(items))

    def _expr_TUPLE(self, node: ASTNode):
        val = node.value
        if val == '()':
            self._emit(MAKE_TUPLE, 0)
            return
        items = self._parse_list_items(val[1:-1]) if val.startswith('(') else []
        for item in items:
            self._compile_simple_expr(item.strip())
        self._emit(MAKE_TUPLE, len(items))

    def _expr_INDEX(self, node: ASTNode):
        val = str(node.value)
        # Find the first top-level bracket
        depth = 0
        bracket = -1
        for i, ch in enumerate(val):
            if ch == '[' and depth == 0:
                bracket = i
                break
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
        if bracket > 0:
            obj_name = val[:bracket].strip()
            # Compile the object - could be dotted name or identifier
            if '.' in obj_name:
                parts = obj_name.rsplit('.', 1)
                self._compile_name(parts[0])
                self._emit(GET_ATTR, self._add_const(parts[1]))
            else:
                self._compile_name(obj_name)
            # Compile the index expression
            idx_expr = val[bracket + 1:-1].strip()
            self._compile_simple_expr(idx_expr)
            self._emit(GET_INDEX)

    def _expr_DOT(self, node: ASTNode):
        parts = node.value.rsplit('.', 1)
        if len(parts) == 2:
            self._compile_name(parts[0])
            idx = self._add_const(parts[1])
            self._emit(GET_ATTR, idx)

    def _expr_DEREF(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])
        self._emit(LOAD_DEREF)

    def _expr_LAMBDA(self, node: ASTNode):
        arg_str = node.value
        body = node.children[0] if node.children else None
        fn = BytecodeFunction(name='<lambda>', arg_names=[a.strip() for a in arg_str.split(',') if a.strip()])
        old_fn = self._current_fn
        self._current_fn = fn
        old_scope = self._scope_stack
        self._scope_stack = [{}]
        for a in fn.arg_names:
            self._declare_var(a)
        if body:
            self._compile_expr(body)
        else:
            self._emit(LOAD_CONST, self._add_const(None))
        self._emit(RETURN)
        self._current_fn = old_fn
        self._scope_stack = old_scope
        fn_idx = len(self.module.functions)
        self.module.functions.append(fn)
        self._emit(MAKE_FN, fn_idx)

    def _expr_KWARG(self, node: ASTNode):
        # keyword args are handled by CALL
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_STAR(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_DSTAR(self, node: ASTNode):
        if node.children:
            self._compile_expr(node.children[0])

    def _expr_PIPE(self, node: ASTNode):
        """pipe: a |> f |> g — compiled as g(f(a))."""
        # Simplified: just compile as expression
        self._compile_simple_expr(str(node.value) if node.value else 'None')

    def _expr_OPTIONAL_CHAIN(self, node: ASTNode):
        """?. operator — simplified to getattr with None check."""
        self._compile_simple_expr(str(node.value) if node.value else 'None')

    def _expr_NULLISH(self, node: ASTNode):
        """?? operator — simplified."""
        self._compile_simple_expr(str(node.value) if node.value else 'None')

    def _expr_BANG(self, node: ASTNode):
        """! unwrap operator."""
        if node.children:
            self._compile_expr(node.children[0])

    # ── helpers ─────────────────────────────────────────────────────
    def _compile_name(self, name: str):
        kind, _ = self._resolve(name)
        idx = self._add_const(name)
        if kind == 'global' or self._current_fn is None:
            self._emit(LOAD_GLOBAL, idx)
        else:
            self._emit(LOAD_VAR, idx)

    def _compile_simple_expr(self, expr: str):
        """Compile a simple string expression (fallback for complex AST nodes)."""
        expr = expr.strip()
        if not expr:
            self._emit(LOAD_CONST, self._add_const(None))
            return
        # literal int
        try:
            self._emit(LOAD_CONST, self._add_const(int(expr)))
            return
        except ValueError:
            pass
        # literal float
        try:
            self._emit(LOAD_CONST, self._add_const(float(expr)))
            return
        except ValueError:
            pass
        # literal string — only match if the ENTIRE expr is a single quoted string
        if len(expr) >= 2 and expr[0] in ('"', "'"):
            quote = expr[0]
            # Scan forward from position 1 to find the matching close quote
            i = 1
            matched_end = -1
            while i < len(expr):
                ch = expr[i]
                if ch == '\\':
                    i += 2  # skip escaped character
                    continue
                if ch == quote:
                    matched_end = i
                    break
                i += 1
            if matched_end == len(expr) - 1:
                inner = expr[1:matched_end]
                self._emit(LOAD_CONST, self._add_const(inner))
                return
        # True/False/None
        if expr == 'True':
            self._emit(LOAD_CONST, self._add_const(True))
            return
        if expr == 'False':
            self._emit(LOAD_CONST, self._add_const(False))
            return
        if expr == 'None':
            self._emit(LOAD_CONST, self._add_const(None))
            return
        # name
        if expr.isidentifier():
            self._compile_name(expr)
            return
        # function call: name(args) — fn pushed first, then args
        if '(' in expr and expr.endswith(')'):
            paren_idx = self._find_top_level_paren(expr)
            if paren_idx is not None:
                # Find the matching close paren
                close_idx = self._find_matching_paren(expr, paren_idx)
                if close_idx is None or close_idx != len(expr) - 1:
                    paren_idx = None  # Not a top-level function call
            if paren_idx is not None:
                fn_name = expr[:paren_idx].strip()
                if fn_name.isidentifier():
                    args_str = expr[paren_idx + 1:close_idx].strip()
                    args = self._parse_list_items(args_str) if args_str else []
                    builtin_map = {
                        'print': 0, 'len': 1, 'str': 2, 'int': 3, 'float': 4,
                        'range': 5, 'type': 6, 'input': 7, 'open': 8,
                        'Ok': 32, 'Err': 33, 'Some': 34,
                        'alloc': 10, 'free': 11, 'panic': 20, 'dbg': 21,
                        'sorted': 40, 'enumerate': 41, 'zip': 42,
                        'min': 44, 'max': 45, 'sum': 46, 'abs': 47,
                        'round': 48, 'chr': 49, 'ord': 50,
                        'hex': 51, 'oct': 52, 'bin': 53, 'hash': 54,
                        'isinstance': 55, 'repr': 56,
                        'term_init': 60, 'term_cleanup': 61, 'term_clear': 62,
                        'term_refresh': 63, 'term_size': 64, 'term_move': 65,
                        'term_write': 66, 'term_color': 67, 'term_getkey': 68,
                        'term_addstr': 69, 'term_border': 70, 'term_hline': 71,
                        'term_vline': 72, 'term_getstr': 73, 'term_attr': 74,
                    }
                    if fn_name in builtin_map:
                        for a in args:
                            self._compile_simple_expr(a.strip())
                        self._emit2(INTRINSIC, builtin_map[fn_name], len(args))
                    else:
                        self._compile_name(fn_name)
                        for a in args:
                            self._compile_simple_expr(a.strip())
                        self._emit1(CALL, len(args))
                    return
        # binary op: find LAST lowest-precedence operator outside parens
        split = self._find_top_level_binop(expr)
        if split is not None:
            op_str, opcode, idx = split
            left = expr[:idx].strip()
            right = expr[idx + len(op_str):].strip()
            if left and right:
                self._compile_simple_expr(left)
                self._compile_simple_expr(right)
                self._emit(opcode)
                return
        # negative
        if expr.startswith('-') and len(expr) > 1 and expr[1] not in ('-', '+', '('):
            self._compile_simple_expr(expr[1:])
            self._emit(NEG)
            return
        # not
        if expr.startswith('not '):
            self._compile_simple_expr(expr[4:])
            self._emit(NOT)
            return
        # attribute access: a.b
        if '.' in expr:
            parts = expr.rsplit('.', 1)
            self._compile_name(parts[0])
            self._emit(GET_ATTR, self._add_const(parts[1]))
            return
        # indexing: a[i]
        if '[' in expr and expr.endswith(']'):
            inner = expr[:expr.rfind('[')]
            idx_expr = expr[expr.rfind('[') + 1:-1]
            self._compile_name(inner)
            self._compile_simple_expr(idx_expr)
            self._emit(GET_INDEX)
            return
        # variable reference (fallback)
        self._compile_name(expr)

    def _find_top_level_paren(self, expr: str) -> 'Optional[int]':
        """Find the position of the first top-level '(' in the expression."""
        depth = 0
        in_string = None
        for i, ch in enumerate(expr):
            if in_string:
                if ch == in_string and (i == 0 or expr[i-1] != '\\'):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == '(':
                if depth == 0:
                    return i
                depth += 1
            elif ch == ')':
                depth -= 1
        return None

    def _find_matching_paren(self, expr: str, open_pos: int) -> 'Optional[int]':
        """Find the matching close paren for an open paren at open_pos."""
        depth = 0
        in_string = None
        for i in range(open_pos, len(expr)):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i-1] != '\\'):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return i
        return None

    def _find_top_level_binop(self, expr: str) -> 'Optional[tuple]':
        """Find the best binary operator to split on, respecting precedence and parentheses.
        Returns (op_str, opcode, position) or None.
        We scan from right to left at the lowest precedence level first
        to ensure correct left-to-right evaluation order."""
        precedence_groups = [
            (1, [('and', AND), ('or', OR)]),
            (2, [('==', EQ), ('!=', NEQ), ('<', LT), ('>', GT), ('<=', LTE), ('>=', GTE), ('in', IN_OP)]),
            (3, [('+', ADD), ('-', SUB)]),
            (4, [('*', MUL), ('//', FLOOR_DIV), ('/', DIV), ('%', MOD)]),
            (5, [('**', POW)]),
        ]
        for _prec, ops in precedence_groups:
            # Sort by length descending so we match longest first
            ops_sorted = sorted(ops, key=lambda x: -len(x[0]))
            for i in range(len(expr) - 1, 0, -1):
                if self._in_string_at(expr, i):
                    continue
                depth = self._paren_depth_at(expr, i)
                if depth > 0:
                    continue
                for op_str, opcode in ops_sorted:
                    if expr[i:i+len(op_str)] == op_str:
                        # Verify this isn't part of a longer operator
                        # Check backward: prev char forming longer op
                        if i > 0 and len(op_str) == 1:
                            prev_char = expr[i-1]
                            if prev_char == op_str[0]:
                                continue
                        # Check forward: next char forming longer op
                        if i + len(op_str) < len(expr) and len(op_str) == 1:
                            next_char = expr[i + len(op_str)]
                            if next_char == op_str[0]:
                                continue
                        left = expr[:i].strip()
                        right = expr[i + len(op_str):].strip()
                        if left and right:
                            return (op_str, opcode, i)
        return None

    def _in_string_at(self, expr: str, pos: int) -> bool:
        """Check if position is inside a string literal."""
        in_string = None
        for i in range(pos):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i-1] != '\\'):
                    in_string = None
            elif ch in ('"', "'"):
                in_string = ch
        return in_string is not None

    def _paren_depth_at(self, expr: str, pos: int) -> int:
        """Return the parenthesis depth at the given position."""
        depth = 0
        in_string = None
        for i in range(pos):
            ch = expr[i]
            if in_string:
                if ch == in_string and (i == 0 or expr[i-1] != '\\'):
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        return depth

    def _parse_list_items(self, s: str) -> List[str]:
        """Parse comma-separated items respecting brackets."""
        items = []
        depth = 0
        current = []
        for ch in s:
            if ch in '([{':
                depth += 1
                current.append(ch)
            elif ch in ')]}':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                items.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            items.append(''.join(current))
        return items

    def _eval_const(self, s: str) -> Any:
        """Evaluate a constant expression at compile time."""
        s = s.strip()
        if s == 'True':
            return True
        if s == 'False':
            return False
        if s == 'None':
            return None
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s
