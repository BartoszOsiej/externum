"""Externum — static analysis (the language's strictness, always on).

`TypeChecker` walks the parsed AST and enforces the rules that make Externum
genuinely difficult to misuse:

1. **Explicit declarations** — every variable must be declared with a type
   annotation (`x: Int`) before use; using an undeclared name is an error.
2. **Static typing** — assignments and returns are checked against declared
   types (literals, inferred expressions, call return types). There is no
   implicit `Int` → `Float` widening: write `1.0` or use `float(x)`.
3. **Immutability by default** — bindings are immutable unless declared
   `mut x: Int = 5`; reassigning an immutable binding is a compile error.
4. **Move semantics** — non-copy values (`List`, `Dict`, `Set`, class
   instances, pointers) are *moved* when assigned or passed to a function;
   using a moved value afterwards is a compile error. `Int`, `Float`, `Str`,
   `Bool` and `Any` are copy types.
5. **Ownership discipline (linear-ish)** — `alloc()` produces a pointer that
   must be `free()`d exactly once; double-free and use-after-free are compile
   errors. Ownership can only be transferred explicitly.
6. **Trait conformance** — `impl Trait for Class` must implement every trait
   method with a matching return type.
7. **`unsafe` blocks** are exempt from all of the above (the escape hatch).

Errors are reported as `ExternumTypeError` with source locations.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from .parser import ASTNode


class ExternumTypeError(Exception):
    """Raised when the static checker rejects a program."""


_KNOWN_BASE = {'Int', 'Float', 'Str', 'Bool', 'Void', 'Any', 'Ptr'}
_BUILTIN_RETURNS = {
    'len': 'Int', 'str': 'Str', 'int': 'Int', 'float': 'Float', 'bool': 'Bool',
    'abs': 'Any', 'sum': 'Any', 'min': 'Any', 'max': 'Any', 'round': 'Int',
    'ord': 'Int', 'chr': 'Str', 'hex': 'Str', 'oct': 'Str',
    'bin': 'Str', 'repr': 'Str', 'sizeof': 'Int',
    'alloc': 'Ptr', 'addr': 'Ptr', 'recv': 'Any', 'chan': 'Any',
    'copy': 'Any', 'list': 'List',
}

# Copy types are cheap to duplicate; moving them would be noise. Everything
# else (List, Dict, Set, Tuple, Optional of non-copy, class instances, Ptr)
# is moved on transfer — using it afterwards is a compile error.
_COPY_TYPES = {'Int', 'Float', 'Str', 'Bool', 'Any'}

# Words that appear inside string-rendered expressions but are never
# variables: Python/Externum keywords and logical operators.
_NON_VARS = {'True', 'False', 'None', 'self', '_',
             'if', 'else', 'elif', 'for', 'in', 'and', 'or', 'not', 'is',
             'while', 'def', 'class', 'return', 'lambda', 'with', 'as',
             'import', 'from', 'try', 'except', 'finally', 'raise',
             'pass', 'break', 'continue', 'del', 'global', 'nonlocal',
             'yield', 'assert', 'match', 'case', 'trait', 'impl', 'unsafe',
             'macro', 'mut', 'range'}


def _base_of(t: Optional[str]) -> Optional[str]:
    """Strip generic arguments: `List[Int]` -> `List`."""
    if not t:
        return None
    return t.split('[')[0].strip()


def _is_ptr(t: Optional[str]) -> bool:
    return _base_of(t) == 'Ptr'


def _is_copy(t: Optional[str]) -> bool:
    if not t:
        return True  # unknown types are treated leniently
    return _base_of(t) in _COPY_TYPES


class _Sym:
    __slots__ = ('type', 'declared', 'line', 'mutable')

    def __init__(self, type_: Optional[str], declared: bool, line: int,
                 mutable: bool = False):
        self.type = type_
        self.declared = declared
        self.line = line
        self.mutable = mutable


class TypeChecker:
    def __init__(self, ast: List[ASTNode], annotations: Dict[str, str],
                 signatures: Dict[str, dict], traits: Dict[str, dict],
                 impls: Dict[Tuple[str, str], list],
                 mutable: Set[str] = None):
        self.ast = ast
        self.annotations = annotations
        self.signatures = signatures
        self.traits = traits
        self.impls = impls
        self.mutable = set(mutable or set())
        self.symbols: Dict[str, _Sym] = {}
        self.pointers: Set[str] = set()   # names currently holding live pointers
        self.freed: Set[str] = set()      # pointers already freed
        self.moved: Set[str] = set()      # values already moved (use-after-move)
        self.globals: Set[str] = set()    # names declared global/nonlocal
        self.errors: List[str] = []
        self._in_unsafe = 0
        self._scope: List[Set[str]] = [set()]
        self._current_ret: Optional[str] = None
        self._check_traits()
        self._check_impls()
        self._check_nodes(self.ast)

    # ------------------------------------------------------------------ helpers
    def _err(self, msg: str, line: int = 0):
        self.errors.append(f'[externum:{line}] {msg}')

    def _enter_scope(self):
        self._scope.append(set())

    def _exit_scope(self):
        for name in self._scope.pop():
            if name in self.globals:
                continue  # global names survive scope exit
            self.symbols.pop(name, None)
            self.pointers.discard(name)
            self.freed.discard(name)
            self.moved.discard(name)

    def _declare(self, name: str, type_: Optional[str], line: int,
                 mutable: bool = False):
        self.symbols[name] = _Sym(type_, True, line, mutable)
        self._scope[-1].add(name)
        if _is_ptr(type_):
            self.pointers.add(name)

    def _lookup(self, name: str, line: int) -> Optional[_Sym]:
        if name in self.moved:
            self._err(f'use of moved value `{name}` — it was transferred', line)
            return None
        sym = self.symbols.get(name)
        if sym is None and self._in_unsafe == 0 and name != '_' \
                and name not in self.globals \
                and name not in ('True', 'False', 'None', 'self') \
                and name not in self.signatures:
            self._err(f'undeclared variable `{name}` — declare it with a type first', line)
            return None
        return sym

    # ------------------------------------------------------------- trait checks
    def _check_traits(self):
        for tname, tdef in self.traits.items():
            seen = set()
            for mname, _params, ret in tdef['methods']:
                if mname in seen:
                    self._err(f'trait `{tname}` declares duplicate method `{mname}`')
                seen.add(mname)
                if ret and _base_of(ret) not in _KNOWN_BASE | {'List', 'Dict', 'Optional'}:
                    self._err(f'trait `{tname}` method `{mname}` has unknown return type `{ret}`')

    def _check_impls(self):
        for (tname, cname), methods in self.impls.items():
            trait = self.traits.get(tname)
            if trait is None:
                self._err(f'impl references unknown trait `{tname}`')
                continue
            trait_methods = {m[0] for m in trait['methods']}
            impl_methods = {m[0] for m in methods}
            missing = trait_methods - impl_methods
            if missing:
                self._err(f'impl `{tname} for {cname}` is missing method(s): {sorted(missing)}')
            # return-type conformance
            trait_ret = {m[0]: m[2] for m in trait['methods']}
            for mname, _p, ret in methods:
                want = trait_ret.get(mname)
                if want and ret and _base_of(ret) != _base_of(want):
                    self._err(
                        f'impl `{tname} for {cname}` method `{mname}` returns `{ret}`, '
                        f'trait requires `{want}`')

    # --------------------------------------------------------------- AST walk
    def _check_nodes(self, nodes: List[ASTNode]):
        for node in nodes:
            self._check_node(node)

    def _check_node(self, node: ASTNode):
        t = node.type
        if t == 'UNSAFE':
            self._in_unsafe += 1
            try:
                self._check_nodes(node.children)
            finally:
                self._in_unsafe -= 1
        elif t == 'ASSIGN':
            self._check_assign(node)
        elif t == 'AUG_ASSIGN':
            self._check_aug_assign(node)
        elif t == 'DECLARE':
            self._declare(node.value, node.children[0].value if node.children else 'Any', 0,
                          mutable=node.value in self.mutable)
        elif t == 'FUNCTION':
            self._check_function(node)
        elif t == 'CLASS':
            self._enter_scope()
            for child in node.children[1:]:
                self._check_node(child)
            self._exit_scope()
        elif t == 'IF':
            self._check_expr(node.children[0])
            self._enter_scope()
            self._check_branches(node.children[1:])
            self._exit_scope()
        elif t == 'ELIF':
            self._check_expr(node.children[0])
            self._check_branches(node.children[1:])
        elif t == 'ELSE':
            self._check_branches(node.children)
        elif t == 'WHILE':
            self._check_expr(node.children[0])
            self._enter_scope()
            self._check_branches(node.children[1:])
            self._exit_scope()
        elif t == 'FOR':
            self._enter_scope()
            # loop variables are implicitly bound (like Rust `for i in ...`)
            if node.value:
                for var in node.value.split(','):
                    var = var.strip()
                    if var and var != '_':
                        self._declare(var, 'Any', 0, mutable=True)
            if node.children and node.children[0].type == 'ITERABLE':
                it = node.children[0].children[0]
                self._check_expr(it)
                self._check_branches(node.children[1:])
            else:
                self._check_branches(node.children)
            self._exit_scope()
        elif t == 'MATCH':
            self._check_expr(node.children[0])
            self._enter_scope()
            for child in node.children[1:]:
                self._check_node(child)
            self._exit_scope()
        elif t == 'CASE':
            # pattern bindings enter the scope
            pat = node.children[0].value if node.children else ''
            for bind in self._pattern_binds(pat):
                self._declare(bind, 'Any', 0)
            for child in node.children[1:]:
                if child.type == 'GUARD':
                    self._check_expr(child.children[0])
                else:
                    self._check_node(child)
        elif t == 'RETURN':
            if node.children:
                self._check_expr(node.children[0])
                if self._current_ret and self._in_unsafe == 0:
                    vtype = self._infer(node.children[0])
                    if vtype and not self._compatible(vtype, self._current_ret):
                        self._err(
                            f'return type `{vtype}` does not match declared `{self._current_ret}`', 0)
        elif t == 'YIELD':
            if node.children:
                self._check_expr(node.children[0])
        elif t == 'RAISE':
            if node.children:
                self._check_expr(node.children[0])
        elif t == 'ASSERT':
            for child in node.children:
                self._check_expr(child)
        elif t == 'DEL':
            for child in node.children:
                self._check_expr(child)
        elif t in ('CALL', 'DEREF'):
            self._check_expr(node)
        elif t == 'EXPRESSION':
            self._check_expr(node)
        elif t == 'TRY':
            for child in node.children:
                self._check_node(child)
        elif t == 'EXCEPT':
            # `except X as e:` binds e as a local
            for child in node.children:
                if child.type == 'AS_VAR':
                    self._declare(child.value, 'Any', 0, mutable=True)
            for child in node.children:
                self._check_node(child)
        elif t == 'GLOBAL':
            for name in node.value.replace(',', ' ').split():
                self.globals.add(name)
        elif t == 'NONLOCAL':
            for name in node.value.replace(',', ' ').split():
                self.globals.add(name)
        elif t == 'IMPORT':
            self._declare_import(node.value)
        elif t in ('TRAIT', 'IMPL', 'PARAMS', 'ITERABLE', 'COND', 'AS_VAR',
                   'OP', 'BREAK', 'CONTINUE', 'PASS',
                   'BASH_BLOCK', 'BASH_COMMAND', 'WITH'):
            pass  # no local checks
        else:
            # statements with expression children — walk generically
            for child in node.children:
                self._check_node(child)

    def _check_branches(self, nodes: List[ASTNode]):
        for node in nodes:
            if node.type in ('ELIF', 'ELSE'):
                self._check_node(node)
            else:
                self._check_node(node)

    def _declare_import(self, value: str):
        """Register names bound by an import statement so they count as
        declared (modules, aliases and `from x import y` symbols)."""
        raw = str(value).strip()
        names = []
        if raw.startswith('import '):
            for part in raw[len('import '):].split(','):
                mod = part.strip().split('.')[0]
                if mod:
                    names.append(mod)
        elif raw.startswith('from '):
            rest = raw[len('from '):]
            if ' import ' in rest:
                _, _, syms = rest.partition(' import ')
                for part in syms.split(','):
                    name = part.strip()
                    if ' as ' in name:
                        name = name.split(' as ')[-1].strip()
                    if name and name != '*':
                        names.append(name)
        for name in names:
            self._declare(name, 'Any', 0, mutable=True)

    def _pattern_binds(self, pattern: str) -> List[str]:
        """Names bound by a case pattern (everything that isn't a literal)."""
        binds = []
        for token in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', pattern):
            if token not in ('True', 'False', 'None') and token != '_':
                binds.append(token)
        return binds

    # --------------------------------------------------------------- functions
    def _check_function(self, node: ASTNode):
        name = node.value
        sig = self.signatures.get(name)
        # Per-node parameter types (attached by the parser) are authoritative:
        # method signatures share one slot per bare name, so `__init__` of a
        # later class would otherwise clobber an earlier one's annotations.
        ptypes = {}
        params_node = node.children[0] if node.children else None
        if params_node is not None:
            for pn in params_node.children or []:
                ptype = pn.children[0].value if pn.children and pn.children[0].value else None
                ptypes[pn.value] = ptype or None
        if sig:
            # fill any names the node didn't carry from the signature
            for pname, ptype in sig['params']:
                if pname.lstrip('*') not in {k.lstrip('*') for k in ptypes}:
                    ptypes[pname] = ptype
        prev_ret = self._current_ret
        self._current_ret = sig.get('ret') if sig else None
        # function-local scope
        self._enter_scope()
        for pname, ptype in ptypes.items():
            clean = pname.lstrip('*')
            # strict language: parameters must carry a type annotation
            if (self._in_unsafe == 0 and ptype is None
                    and clean != 'self' and not pname.startswith('*')):
                self._err(f'parameter `{clean}` of `{name}` needs a type annotation', 0)
            self._declare(clean, ptype, 0, mutable=True)  # params are locals
        for child in node.children[1:]:
            self._check_node(child)
        self._exit_scope()
        self._current_ret = prev_ret

    # --------------------------------------------------------------- assigns
    def _check_assign(self, node: ASTNode):
        if node.value:  # tuple target "a, b = ..."
            for part in node.value.split(','):
                part = part.strip()
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', part):
                    self._assign_target(part, None, node.children[0] if node.children else None, 0)
            return
        if not node.children:
            return
        target = node.children[0]
        value = node.children[1] if len(node.children) > 1 else None
        if target.type == 'IDENTIFIER':
            self._assign_target(target.value, None, value, 0)
        elif target.type == 'DEREF':
            ptr = self._deref_target_name(target)
            if ptr and ptr in self.freed:
                self._err(f'write through freed pointer `{ptr}`', 0)
            elif value:
                self._check_expr(value)
        elif target.type in ('INDEX', 'DOT'):
            if value:
                self._check_expr(value)
        else:
            if value:
                self._check_expr(value)

    def _deref_target_name(self, node: ASTNode) -> Optional[str]:
        if node.children and node.children[0].type == 'IDENTIFIER':
            return node.children[0].value
        return None

    def _assign_target(self, name: str, type_: Optional[str], value: ASTNode, line: int):
        existing = self.symbols.get(name)
        if existing is None:
            if self._in_unsafe > 0:
                # unsafe block: implicit Any declaration is allowed
                self._declare(name, 'Any', line, mutable=True)
                existing = self.symbols.get(name)
            else:
                declared_type = self.annotations.get(name)
                if declared_type or name in self.globals:
                    self._declare(name, declared_type or 'Any', line,
                                  mutable=name in self.mutable or name in self.globals)
                    existing = self.symbols.get(name)
                else:
                    self._err(f'`{name}` is not declared — add `{name}: Type` first', line)
                    return
        else:
            # immutability: reassigning a non-`mut` binding is an error
            if self._in_unsafe == 0 and not existing.mutable and name not in self.globals:
                self._err(
                    f'cannot reassign immutable binding `{name}` — declare `mut {name}: ...`', line)
                return
        if value is not None and existing.type and self._in_unsafe == 0:
            vtype = self._infer(value)
            if vtype and not self._compatible(vtype, existing.type):
                self._err(
                    f'cannot assign `{vtype}` to `{name}: {existing.type}`', line)
        # move semantics: `b = a` moves non-copy `a` into the new binding
        if value is not None and value.type == 'IDENTIFIER' and value.value != name:
            src = self.symbols.get(value.value)
            if src is not None and not _is_copy(src.type) and value.value not in self.moved \
                    and value.value not in self.globals and self._in_unsafe == 0:
                self.moved.add(value.value)
                self.symbols.pop(value.value, None)
                self._scope[-1].discard(value.value)
                self.pointers.discard(value.value)

    def _check_aug_assign(self, node: ASTNode):
        if node.children and node.children[0].type == 'IDENTIFIER':
            target = node.children[0].value
            existing = self.symbols.get(target)
            if existing is not None and self._in_unsafe == 0 \
                    and not existing.mutable and target not in self.globals:
                self._err(
                    f'cannot mutate immutable binding `{target}` — declare `mut {target}: ...`', 0)
            else:
                self._assign_target(target, None, None, 0)

    # --------------------------------------------------------------- exprs
    def _check_expr(self, node: ASTNode):
        if node is None:
            return
        t = node.type
        if t == 'IDENTIFIER':
            self._lookup(node.value, 0)
        elif t == 'CALL':
            for child in node.children:
                self._check_expr(child)
            self._check_call(node)
        elif t == 'DEREF':
            self._check_deref(node)
        elif t == 'INDEX' or t == 'DOT':
            # string-rendered: verify referenced names exist. Names that
            # follow a dot are attributes/methods, not variables — the
            # negative lookbehind skips them and, crucially, does not let
            # the scan re-match *inside* a name (sys.argv -> only `sys`).
            for m in re.finditer(r'(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|\[)', str(node.value)):
                name = m.group(1)
                if name in self.signatures or name in _BUILTIN_RETURNS:
                    continue
                if name in _NON_VARS:
                    continue
                self._lookup(name, 0)
        elif t in ('EXPRESSION', 'LIST', 'DICT', 'SET', 'TUPLE'):
            self._check_container(node)
        elif t == 'LAMBDA':
            # lambda parameters are implicitly bound
            if node.value:
                for pname in re.split(r'[,\s]+', node.value.strip()):
                    pname = pname.lstrip('*')
                    if pname:
                        self._declare(pname, 'Any', 0, mutable=True)
            for child in node.children:
                self._check_expr(child)
        elif t in ('KWARG', 'STAR', 'DSTAR'):
            for child in node.children:
                self._check_expr(child)

    def _check_container(self, node: ASTNode):
        """Check a string-rendered literal/expression node, honouring
        comprehension bindings (`for x in ...`) and lambda params."""
        s = str(node.value)
        # strip string literals so their words are never read as variables
        s = re.sub(r'""".*?"""', '', s, flags=re.DOTALL)
        s = re.sub(r"'''.*?'''", '', s, flags=re.DOTALL)
        s = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '', s)
        s = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", '', s)
        # comprehension variables:  [expr for x in it ...]
        comp_vars = set(re.findall(r'\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b', s))
        # names that are bound by the comprehension itself
        for name in re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', s):
            if name in self.signatures or name in _BUILTIN_RETURNS:
                continue
            if name in _NON_VARS:
                continue
            if name in comp_vars:
                continue  # bound by the comprehension
            # skip attribute/method names that follow a dot
            prev = s[max(0, s.find(name) - 1)] if s.find(name) > 0 else ''
            if prev == '.':
                continue
            self._lookup(name, 0)
        for child in node.children:
            self._check_expr(child)

    def _check_call(self, node: ASTNode):
        fn = node.value
        if fn == 'free' and node.children:
            arg = node.children[0]
            if arg.type == 'IDENTIFIER':
                name = arg.value
                if name in self.freed:
                    self._err(f'double free of pointer `{name}`', 0)
                if name not in self.pointers and self._in_unsafe == 0:
                    self._err(f'free() of `{name}` which is not a live pointer', 0)
                else:
                    self.freed.add(name)
                    self.pointers.discard(name)
            elif self._in_unsafe == 0:
                self._err('free() expects a pointer variable', 0)
        elif fn == 'alloc' and node.children:
            arg = node.children[0]
            if arg.type == 'IDENTIFIER':
                type_name = arg.value
                if type_name not in _KNOWN_BASE | {'List', 'Dict', 'Optional'}:
                    self._err(f'alloc() of unknown type `{type_name}`', 0)
        # move semantics: passing a non-copy variable to a user function moves it
        if fn in self.signatures and self._in_unsafe == 0:
            for arg in node.children:
                if arg.type == 'IDENTIFIER' and arg.value not in self.globals:
                    src = self.symbols.get(arg.value)
                    if src is not None and not _is_copy(src.type) \
                            and arg.value not in self.moved:
                        self.moved.add(arg.value)
                        self.symbols.pop(arg.value, None)
                        self._scope[-1].discard(arg.value)
                        self.pointers.discard(arg.value)

    def _check_deref(self, node: ASTNode):
        child = node.children[0] if node.children else None
        if child and child.type == 'IDENTIFIER':
            name = child.value
            sym = self.symbols.get(name)
            if sym is None:
                self._lookup(name, 0)
            elif not _is_ptr(sym.type):
                self._err(f'cannot dereference `{name}`: not a Ptr', 0)
            if name in self.freed:
                self._err(f'use-after-free: dereference of freed pointer `{name}`', 0)

    # --------------------------------------------------------------- inference
    def _infer(self, node: ASTNode) -> Optional[str]:
        """Best-effort type inference for expressions."""
        if node is None:
            return None
        t = node.type
        if t == 'NUMBER':
            return 'Float' if isinstance(node.value, float) else 'Int'
        if t == 'BINARY_NUMBER':
            return 'Int'
        if t == 'STRING':
            return 'Str'
        if t == 'IDENTIFIER':
            if node.value == 'True' or node.value == 'False':
                return 'Bool'
            if node.value == 'None':
                return 'Optional'
            sym = self.symbols.get(node.value)
            return sym.type if sym else None
        if t == 'CALL':
            ret = self.signatures.get(node.value, {}).get('ret') if node.value in self.signatures else None
            if ret:
                return ret
            return _BUILTIN_RETURNS.get(node.value)
        if t == 'DEREF':
            child = node.children[0] if node.children else None
            if child and child.type == 'IDENTIFIER':
                sym = self.symbols.get(child.value)
                if sym and _is_ptr(sym.type):
                    inner = sym.type[4:-1] if sym.type.startswith('Ptr[') else 'Any'
                    return inner or 'Any'
            return 'Any'
        if t in ('LIST', 'SET'):
            return f'{t.title()}[Any]' if t == 'LIST' else 'Set'
        if t == 'DICT':
            return 'Dict'
        if t == 'TUPLE':
            return 'Tuple'
        if t == 'LAMBDA':
            return 'Any'
        if t == 'EXPRESSION':
            return self._infer_str(str(node.value))
        if t in ('INDEX', 'DOT'):
            return self._infer_str(str(node.value))
        return None

    def _infer_str(self, s: str) -> Optional[str]:
        s = s.strip()
        if not s:
            return None
        if re.fullmatch(r'-?\d+', s):
            return 'Int'
        if re.fullmatch(r'-?\d+\.\d+', s):
            return 'Float'
        if s.startswith(('"', "'", 'f"', "f'", 'b"', "b'")):
            return 'Str'
        if s in ('True', 'False'):
            return 'Bool'
        if s == 'None':
            return 'Optional'
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', s):
            sym = self.symbols.get(s)
            return sym.type if sym else None
        m = re.fullmatch(r'\((.*)\)', s)
        if m:
            return self._infer_str(m.group(1))
        # user/builtin function call FIRST: `fact(n - 1)` must not be eaten
        # by the binary-op regex (the `-` inside the parens)
        m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\((.*)\)', s)
        if m:
            fname = m.group(1)
            sig = self.signatures.get(fname)
            if sig and sig.get('ret'):
                return sig['ret']
            return _BUILTIN_RETURNS.get(fname)
        # method call: `receiver.method(...)` — keep the receiver's type if
        # it is a Str (str methods return str)
        m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_.]*)\.[A-Za-z_][A-Za-z0-9_]*\((.*)\)', s)
        if m:
            recv = m.group(1)
            recv_type = self._infer_str(recv)
            if recv_type == 'Str':
                return 'Str'
            if recv_type == 'List':
                return 'List'
            return 'Any'
        # slice/index access: `recv[i]` has the *element* type of `recv`
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*\[[^\]]*\]', s):
            recv = s.split('[', 1)[0]
            recv_type = self._infer_str(recv)
            if recv_type:
                flat = recv_type.replace(' ', '')
                if flat.startswith('List['):
                    return flat[5:-1] or 'Any'
                return recv_type
            return 'Any'
        if s.startswith('alloc(') or s.startswith('addr('):
            return 'Ptr'
        # binary ops — but first protect slices with `-` inside (s[a-b:c])
        if re.search(r'\[[^\]]*[-+*/][^\]]*\]', s):
            # a slice with arithmetic inside: split on the outermost +/-
            for op in ('+', '-'):
                parts = s.split(op)
                if len(parts) == 2:
                    a, b = self._infer_str(parts[0]), self._infer_str(parts[1])
                    if a == 'Str' or b == 'Str':
                        return 'Str'
                    if a in ('Float',) or b in ('Float',):
                        return 'Float'
                    if a == 'Int' and b == 'Int':
                        return 'Int'
                    return 'Any'
        # word operators `is`/`in` need word boundaries so that `in` inside
        # `int(ch)` is not mistaken for the `in` operator
        m = re.fullmatch(r'(.+?)\s*(==|!=|<=|>=|<|>|\bis\b|\bin\b|≈|≠)\s*(.+)', s)
        if m:
            return 'Bool'
        m = re.fullmatch(r'(.+?)\s*(\+|-|\*|/|//|%|\*\*)\s*(.+)', s)
        if m:
            a, b = self._infer_str(m.group(1)), self._infer_str(m.group(3))
            if a == 'Str' or (b == 'Str' and m.group(2) == '+'):
                return 'Str'
            if a in ('Float',) or b in ('Float',):
                return 'Float'
            if a == 'Int' and b == 'Int':
                return 'Int'
            # arithmetic on a known scalar with an unknown operand stays
            # the scalar's type (e.g. loop variables are Any, but `s + n`
            # with s: Int is still Int)
            if a == 'Int' or b == 'Int':
                return 'Int'
            return 'Any'
        if s.startswith('recv('):
            return 'Any'
        if s.startswith('chan('):
            return 'Any'
        if s.startswith('copy('):
            inner = s[5:-1].strip()
            return self._infer_str(inner) if inner else 'Any'
        return None

    def _compatible(self, value_type: str, declared: str) -> bool:
        """Can a value of `value_type` be stored in `declared`? Strict:
        no implicit widening, no implicit conversions."""
        vbase, dbase = _base_of(value_type), _base_of(declared)
        if dbase == 'Any':
            return True
        if dbase == 'Optional':
            return vbase in ('Any', 'Optional', 'None')
        if vbase == 'Optional' and dbase != 'Optional':
            return False
        return vbase == dbase

    # ------------------------------------------------------------------ result
    def check(self) -> List[str]:
        return self.errors

    def ok(self) -> bool:
        return not self.errors
