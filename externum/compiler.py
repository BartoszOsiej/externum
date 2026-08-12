"""Compiler for Externum v3: AST -> Python / Bash / binary targets."""

import ast as _ast
import re
from typing import List
from .parser import ASTNode


class Compiler:
    def __init__(self, ast: List[ASTNode]):
        self.ast = ast
        self.output = {'python': [], 'binary': [], 'bash': []}
        self.indent = 0

    def compile(self, target: str = 'all'):
        for node in self.ast:
            self._compile_node(node)

        if self._has_bash():
            self.output['python'].insert(0, 'import subprocess')

        if target == 'all':
            return {
                'python': '\n'.join(self.output['python']),
                'bash': '\n'.join(self.output['bash']),
                'binary': '\n'.join(self.output['binary']),
            }
        return self.output.get(target, '')

    def _has_bash(self) -> bool:
        return self._has_bash_in(self.ast)

    def _has_bash_in(self, nodes: List[ASTNode]) -> bool:
        for node in nodes:
            if node.type in ('BASH_BLOCK', 'BASH_COMMAND'):
                return True
            if node.children and self._has_bash_in(node.children):
                return True
        return False

    def _i(self) -> str:
        return '    ' * self.indent

    # ---------------------------------------------------------------- dispatch
    def _compile_node(self, node: ASTNode):
        method = getattr(self, f'_compile_{node.type}', None)
        if method:
            method(node)

    def _compile_OP(self, node: ASTNode):
        pass

    def _compile_ITERABLE(self, node: ASTNode):
        pass

    def _compile_PARAMS(self, node: ASTNode):
        pass

    def _compile_COND(self, node: ASTNode):
        pass

    def _compile_AS_VAR(self, node: ASTNode):
        pass

    # -------------------------------------------------------------- statements
    def _compile_ASSIGN(self, node: ASTNode):
        if node.value:
            target = node.value
            val = self._value_to_str(node.children[0]) if node.children else 'None'
        else:
            target = self._value_to_str(node.children[0]) if node.children else 'None'
            val = self._value_to_str(node.children[1]) if len(node.children) > 1 else 'None'
        self.output['python'].append(f'{self._i()}{target} = {val}')

    def _compile_AUG_ASSIGN(self, node: ASTNode):
        target = self._value_to_str(node.children[0]) if node.children else 'x'
        op = node.children[2].value if len(node.children) > 2 else '+'
        val = self._value_to_str(node.children[1]) if len(node.children) > 1 else '0'
        self.output['python'].append(f'{self._i()}{target} {op} {val}')

    def _compile_FUNCTION(self, node: ASTNode):
        params = ''
        if node.children and node.children[0].type == 'PARAMS':
            params = node.children[0].value
        self.output['python'].append(f'{self._i()}def {node.value}({params}):')
        self.indent += 1
        for child in node.children[1:]:
            self._compile_node(child)
        self.indent -= 1

    def _compile_CLASS(self, node: ASTNode):
        bases = ''
        if node.children and node.children[0].type == 'PARAMS':
            bases = node.children[0].value
        if bases:
            header = f'class {node.value}({bases}):'
        else:
            header = f'class {node.value}:'
        self.output['python'].append(f'{self._i()}{header}')
        self.indent += 1
        for child in node.children[1:]:
            self._compile_node(child)
        self.indent -= 1

    def _compile_IF(self, node: ASTNode):
        cond = self._value_to_str(node.children[0]) if node.children else 'True'
        self.output['python'].append(f'{self._i()}if {cond}:')
        self.indent += 1
        for child in node.children[1:]:
            if child.type in ('ELIF', 'ELSE'):
                continue
            self._compile_node(child)
        self.indent -= 1
        for child in node.children[1:]:
            if child.type == 'ELIF':
                self._compile_ELIF(child)
            elif child.type == 'ELSE':
                self._compile_ELSE(child)

    def _compile_ELIF(self, node: ASTNode):
        cond = self._value_to_str(node.children[0]) if node.children else 'True'
        self.output['python'].append(f'{self._i()}elif {cond}:')
        self.indent += 1
        for child in node.children[1:]:
            if child.type in ('ELIF', 'ELSE'):
                continue
            self._compile_node(child)
        self.indent -= 1
        for child in node.children[1:]:
            if child.type == 'ELIF':
                self._compile_ELIF(child)
            elif child.type == 'ELSE':
                self._compile_ELSE(child)

    def _compile_ELSE(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}else:')
        self.indent += 1
        for child in node.children:
            self._compile_node(child)
        self.indent -= 1

    def _compile_FOR(self, node: ASTNode):
        var = node.value or '_'
        body = node.children
        if node.children and node.children[0].type == 'ITERABLE':
            iterable = self._value_to_str(node.children[0].children[0])
            body = node.children[1:]
        else:
            iterable = 'range(10)'
        self.output['python'].append(f'{self._i()}for {var} in {iterable}:')
        self.indent += 1
        for child in body:
            self._compile_node(child)
        self.indent -= 1

    def _compile_WHILE(self, node: ASTNode):
        cond = self._value_to_str(node.children[0]) if node.children else 'True'
        self.output['python'].append(f'{self._i()}while {cond}:')
        self.indent += 1
        for child in node.children[1:]:
            self._compile_node(child)
        self.indent -= 1

    def _compile_TRY(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}try:')
        self.indent += 1
        for child in node.children:
            if child.type in ('EXCEPT', 'TRY_ELSE', 'FINALLY'):
                continue
            self._compile_node(child)
        self.indent -= 1
        for child in node.children:
            if child.type == 'EXCEPT':
                self._compile_EXCEPT(child)
        for child in node.children:
            if child.type == 'TRY_ELSE':
                self._compile_TRY_ELSE(child)
        for child in node.children:
            if child.type == 'FINALLY':
                self._compile_FINALLY(child)

    def _compile_EXCEPT(self, node: ASTNode):
        cond = None
        var = None
        body = []
        for child in node.children:
            if child.type == 'COND':
                cond = child.children[0] if child.children else None
            elif child.type == 'AS_VAR':
                var = child.value
            else:
                body.append(child)
        header = 'except'
        if cond is not None:
            header += f' {self._value_to_str(cond)}'
        if var:
            header += f' as {var}'
        self.output['python'].append(f'{self._i()}{header}:')
        self.indent += 1
        for child in body:
            self._compile_node(child)
        self.indent -= 1

    def _compile_TRY_ELSE(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}else:')
        self.indent += 1
        for child in node.children:
            self._compile_node(child)
        self.indent -= 1

    def _compile_FINALLY(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}finally:')
        self.indent += 1
        for child in node.children:
            self._compile_node(child)
        self.indent -= 1

    def _compile_WITH(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}with {node.value}:')
        self.indent += 1
        for child in node.children:
            self._compile_node(child)
        self.indent -= 1

    def _compile_IMPORT(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}{node.value}')

    def _compile_RETURN(self, node: ASTNode):
        if node.children:
            self.output['python'].append(f'{self._i()}return {self._value_to_str(node.children[0])}')
        else:
            self.output['python'].append(f'{self._i()}return')

    def _compile_YIELD(self, node: ASTNode):
        if node.children:
            self.output['python'].append(f'{self._i()}yield {self._value_to_str(node.children[0])}')
        else:
            self.output['python'].append(f'{self._i()}yield')

    def _compile_RAISE(self, node: ASTNode):
        if node.children:
            self.output['python'].append(f'{self._i()}raise {self._value_to_str(node.children[0])}')
        else:
            self.output['python'].append(f'{self._i()}raise')

    def _compile_ASSERT(self, node: ASTNode):
        if len(node.children) > 1:
            self.output['python'].append(
                f'{self._i()}assert {self._value_to_str(node.children[0])}, {self._value_to_str(node.children[1])}')
        else:
            self.output['python'].append(f'{self._i()}assert {self._value_to_str(node.children[0])}')

    def _compile_DEL(self, node: ASTNode):
        if node.children:
            self.output['python'].append(f'{self._i()}del {self._value_to_str(node.children[0])}')

    def _compile_GLOBAL(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}global {node.value}')

    def _compile_NONLOCAL(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}nonlocal {node.value}')

    def _compile_BREAK(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}break')

    def _compile_CONTINUE(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}continue')

    def _compile_PASS(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}pass')

    # ------------------------------------------------------------- expressions
    def _compile_NUMBER(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}{node.value}')

    def _compile_BINARY_NUMBER(self, node: ASTNode):
        bs = bin(node.value)[2:]
        self.output['python'].append(f'{self._i()}int("{bs}", 2)')
        self.output['binary'].append(bs)

    def _compile_IDENTIFIER(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}{node.value}')

    def _compile_STRING(self, node: ASTNode):
        self.output['python'].append(f'{self._i()}{self._string_repr(node.value)}')

    def _compile_EXPRESSION(self, node: ASTNode):
        val = node.value
        if isinstance(val, str):
            self.output['python'].append(f'{self._i()}{val}')
            for m in re.findall(r'int\("([01]+)", 2\)', val):
                self.output['binary'].append(m)

    def _compile_CALL(self, node: ASTNode):
        args = ', '.join(self._value_to_str(c) for c in node.children)
        self.output['python'].append(f'{self._i()}{node.value}({args})')

    # ------------------------------------------------------------- bash targets
    def _compile_BASH_BLOCK(self, node: ASTNode):
        code = node.value.strip()
        self.output['bash'].append(code)
        escaped = code.replace('"', '\\"')
        self.output['python'].append(f'{self._i()}subprocess.run("{escaped}", shell=True)')

    def _compile_BASH_COMMAND(self, node: ASTNode):
        cmd = ' '.join(c.value for c in node.children if hasattr(c, 'value'))
        self.output['bash'].append(cmd)
        escaped = cmd.replace('"', '\\"')
        self.output['python'].append(f'{self._i()}subprocess.run("{escaped}", shell=True)')

    # ---------------------------------------------------------------- helpers
    def _string_repr(self, value) -> str:
        """Emit a string literal. f-strings pass through as-is."""
        if isinstance(value, str):
            s = value.strip()
            if len(s) > 1 and s[0] in 'fFrRbBuU' and s[1] in ('"', "'"):
                return value  # keep prefix + quotes raw (valid Python)
            if s.startswith(('"""', "'''")):
                return value  # triple-quoted raw
            try:
                return repr(_ast.literal_eval(value))
            except (ValueError, SyntaxError):
                return repr(value)
        return repr(value)

    def _value_to_str(self, node: ASTNode) -> str:
        if not node:
            return 'None'
        t = node.type
        if t == 'NUMBER':
            return str(node.value)
        if t == 'BINARY_NUMBER':
            return f'int("{bin(node.value)[2:]}", 2)'
        if t == 'STRING':
            return self._string_repr(node.value)
        if t == 'IDENTIFIER':
            return node.value
        if t in ('EXPRESSION', 'INDEX', 'DOT', 'LIST', 'DICT', 'SET', 'TUPLE',
                 'UNKNOWN'):
            return str(node.value)
        if t == 'CALL':
            args = ', '.join(self._value_to_str(c) for c in node.children)
            return f'{node.value}({args})'
        if t == 'KWARG':
            return f'{node.value}={self._value_to_str(node.children[0]) if node.children else "None"}'
        if t == 'STAR':
            return f'*{self._value_to_str(node.children[0]) if node.children else ""}'
        if t == 'DSTAR':
            return f'**{self._value_to_str(node.children[0]) if node.children else ""}'
        if t == 'LAMBDA':
            body = self._value_to_str(node.children[0]) if node.children else 'None'
            return f'lambda {node.value}: {body}'
        return str(node.value)
