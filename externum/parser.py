"""Parser for Externum v3 — builds an AST from the token stream.

The grammar is a Python-flavoured superset (indentation based) with native
bash integration. Statements: assignments, functions, classes, if/elif/else,
while, for-in, try/except/else/finally, with, import, raise, assert, del,
yield, global, nonlocal, return, break, continue, pass, bash blocks and
expressions. Expressions support full operator precedence, unary operators,
ternary conditionals, lambdas, literals (list/dict/set/tuple), indexing and
slicing, member access, method calls, keyword/star args and comprehensions.
"""

import re
from typing import List
from dataclasses import dataclass, field
from .lexer import Token

@dataclass
class ASTNode:
    type: str
    value: any = None
    children: List['ASTNode'] = field(default_factory=list)


# Operator precedence — higher binds tighter (mirrors Python).
_PRECEDENCE = {
    '||': 1, 'OR': 1,
    '&&': 2, 'AND': 2,
    '==': 4, '!=': 4, '<': 4, '>': 4, '<=': 4, '>=': 4, 'IS': 4, 'IN': 4,
    '|': 5, '^': 6, '&': 7,
    '<<': 8, '>>': 8,
    '+': 9, '-': 9,
    '*': 10, '/': 10, '//': 10, '%': 10,
    '**': 11,
}

# Token type names produced by the lexer -> operator symbol.
_OP_TYPES = {
    'PLUS': '+', 'MINUS': '-', 'TIMES': '*', 'DIVIDE': '/',
    'POWER': '**', 'MOD': '%',
}

# Token values/types that are not valid Python operators.
_OP_TO_PY = {'&&': 'and', '||': 'or', 'AND': 'and', 'OR': 'or', 'IS': 'is', 'IN': 'in'}

# Strip type annotations from parameter lists: `n: Int` -> `n`.
_PARAM_ANNOTATION = re.compile(r':\s*[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?')

# Highest binary precedence (used for unary prefix operands).
_UNARY_BIND = 10


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.ast: List[ASTNode] = []
        self._comp_depth = 0  # inside a comprehension -> no ternary

    # ------------------------------------------------------------- top level
    def parse(self) -> List[ASTNode]:
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type in ('NEWLINE', 'INDENT', 'DEDENT'):
                self.pos += 1
                continue
            self.ast.append(self._parse_statement())
        return self.ast

    # -------------------------------------------------------------- statements
    def _parse_statement(self) -> ASTNode:
        tok = self.tokens[self.pos]
        t = tok.type
        if t == 'BASH_BLOCK':
            self.pos += 1
            return ASTNode('BASH_BLOCK', value=tok.value)
        if t == 'BASH_COMMAND':
            return self._parse_bash_command()
        if t == 'DEF':
            return self._parse_function_def()
        if t == 'CLASS':
            return self._parse_class_def()
        if t == 'IF':
            return self._parse_if_stmt()
        if t == 'FOR':
            return self._parse_for_stmt()
        if t == 'WHILE':
            return self._parse_while_stmt()
        if t == 'TRY':
            return self._parse_try_stmt()
        if t == 'WITH':
            return self._parse_with_stmt()
        if t in ('IMPORT', 'FROM'):
            return self._parse_import_stmt()
        if t == 'RETURN':
            self.pos += 1
            node = ASTNode('RETURN')
            if self.pos < len(self.tokens) and self.tokens[self.pos].type != 'NEWLINE':
                node.children.append(self._parse_expression())
            return node
        if t == 'YIELD':
            self.pos += 1
            node = ASTNode('YIELD')
            if self.pos < len(self.tokens) and self.tokens[self.pos].type != 'NEWLINE':
                node.children.append(self._parse_expression())
            return node
        if t == 'RAISE':
            self.pos += 1
            node = ASTNode('RAISE')
            if self.pos < len(self.tokens) and self.tokens[self.pos].type != 'NEWLINE':
                node.children.append(self._parse_expression())
            return node
        if t == 'ASSERT':
            self.pos += 1
            node = ASTNode('ASSERT', children=[self._parse_expression()])
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                self.pos += 1
                node.children.append(self._parse_expression())
            return node
        if t == 'DEL':
            self.pos += 1
            return ASTNode('DEL', children=[self._parse_expression()])
        if t in ('GLOBAL', 'NONLOCAL'):
            self.pos += 1
            names = []
            while self.pos < len(self.tokens) and self.tokens[self.pos].type != 'NEWLINE':
                if self.tokens[self.pos].type == 'COMMA':
                    names.append(', ')
                else:
                    names.append(self.tokens[self.pos].value)
                self.pos += 1
            return ASTNode(t, value=''.join(names))
        if t in ('BREAK', 'CONTINUE', 'PASS'):
            self.pos += 1
            return ASTNode(t, value=tok.value)
        return self._parse_assignment_or_expr()

    def _parse_assignment_or_expr(self) -> ASTNode:
        expr = self._parse_expression()
        if self.pos < len(self.tokens):
            nxt = self.tokens[self.pos]
            # tuple unpacking target:  a, b = 1, 2
            if nxt.type == 'COMMA' and expr.type in ('IDENTIFIER', 'INDEX', 'DOT'):
                targets = [expr]
                while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                    self.pos += 1
                    targets.append(self._parse_expression())
                if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'ASSIGN':
                    self.pos += 1
                    val = self._parse_expression()
                    if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                        parts = [self._node_to_str(val)]
                        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                            self.pos += 1
                            parts.append(self._node_to_str(self._parse_expression()))
                        val = ASTNode('EXPRESSION', value=', '.join(parts))
                    tgt = ', '.join(self._node_to_str(t) for t in targets)
                    return ASTNode('ASSIGN', value=tgt, children=[val])
                return ASTNode('EXPRESSION',
                               value=f'({chr(44)}{chr(32)}'.join(
                                   self._node_to_str(t) for t in targets) + ')')
            if nxt.type == 'ASSIGN' and expr.type in ('IDENTIFIER', 'INDEX', 'DOT'):
                self.pos += 1
                val = self._parse_expression()
                return ASTNode('ASSIGN', children=[expr, val])
            if nxt.type in ('+=', '-=', '*=', '/=', '//=', '**=', '&=', '|=', '^=', '<<=', '>>='):
                op = nxt.value
                self.pos += 1
                val = self._parse_expression()
                return ASTNode('AUG_ASSIGN', children=[expr, val, ASTNode('OP', value=op)])
        return expr

    # --------------------------------------------------------- compound stmts
    def _parse_function_def(self) -> ASTNode:
        self.pos += 1  # DEF
        name = self.tokens[self.pos].value
        self.pos += 1
        params = ''
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'LPAREN':
            params = self._parse_params()
        self._skip_to_colon()
        body = self._parse_block()
        return ASTNode('FUNCTION', value=name,
                       children=[ASTNode('PARAMS', value=params)] + body)

    def _parse_class_def(self) -> ASTNode:
        self.pos += 1  # CLASS
        name = self.tokens[self.pos].value
        self.pos += 1
        bases = ''
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'LPAREN':
            bases = self._parse_params()
        self._skip_to_colon()
        body = self._parse_block()
        return ASTNode('CLASS', value=name,
                       children=[ASTNode('PARAMS', value=bases)] + body)

    def _parse_if_stmt(self) -> ASTNode:
        self.pos += 1  # IF
        cond = self._parse_expression()
        self._skip_to_colon()
        body = self._parse_block()
        node = ASTNode('IF', children=[cond] + body)
        last = node
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'ELIF':
                self.pos += 1
                c = self._parse_expression()
                self._skip_to_colon()
                b = self._parse_block()
                branch = ASTNode('ELIF', children=[c] + b)
                last.children.append(branch)
                last = branch
            elif tok.type == 'ELSE':
                self.pos += 1
                b = self._parse_block()
                last.children.append(ASTNode('ELSE', children=b))
                break
            else:
                break
        return node

    def _parse_for_stmt(self) -> ASTNode:
        self.pos += 1  # FOR
        vars_ = []
        iterable = None
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'IDENTIFIER' and not vars_ or (vars_ and tok.type == 'IDENTIFIER' and self.tokens[self.pos - 1].type == 'COMMA'):
                vars_.append(tok.value)
                self.pos += 1
            elif tok.type == 'COMMA':
                self.pos += 1
            elif tok.type == 'IN':
                self.pos += 1
                iterable = self._parse_expression()
                break
            else:
                self.pos += 1
        self._skip_to_colon()
        body = self._parse_block()
        children = [ASTNode('ITERABLE', children=[iterable])] if iterable is not None else []
        children += body
        return ASTNode('FOR', value=', '.join(vars_) if vars_ else None, children=children)

    def _parse_while_stmt(self) -> ASTNode:
        self.pos += 1  # WHILE
        cond = self._parse_expression()
        self._skip_to_colon()
        body = self._parse_block()
        return ASTNode('WHILE', children=[cond] + body)

    def _parse_try_stmt(self) -> ASTNode:
        self.pos += 1  # TRY
        self._skip_to_colon()
        node = ASTNode('TRY', children=self._parse_block())
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'EXCEPT':
                self.pos += 1
                branch = []
                if self.tokens[self.pos].type != 'COLON':
                    cond = self._parse_expression()
                    branch.append(ASTNode('COND', children=[cond]))
                    if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'AS':
                        self.pos += 1
                        branch.append(ASTNode('AS_VAR', value=self.tokens[self.pos].value))
                        self.pos += 1
                self._skip_to_colon()
                branch += self._parse_block()
                node.children.append(ASTNode('EXCEPT', children=branch))
            elif tok.type == 'ELSE':
                self.pos += 1
                self._skip_to_colon()
                node.children.append(ASTNode('TRY_ELSE', children=self._parse_block()))
            elif tok.type == 'FINALLY':
                self.pos += 1
                self._skip_to_colon()
                node.children.append(ASTNode('FINALLY', children=self._parse_block()))
                break
            else:
                break
        return node

    def _parse_with_stmt(self) -> ASTNode:
        self.pos += 1  # WITH
        items = []
        while self.pos < len(self.tokens):
            expr = self._parse_expression()
            var = None
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'AS':
                self.pos += 1
                var = self.tokens[self.pos].value
                self.pos += 1
            items.append(f'{self._node_to_str(expr)}' + (f' as {var}' if var else ''))
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                self.pos += 1
                continue
            break
        self._skip_to_colon()
        body = self._parse_block()
        return ASTNode('WITH', value=', '.join(items), children=body)

    def _parse_import_stmt(self) -> ASTNode:
        toks = []
        while self.pos < len(self.tokens) and self.tokens[self.pos].type != 'NEWLINE':
            toks.append(self.tokens[self.pos])
            self.pos += 1
        parts = []
        for i, t in enumerate(toks):
            if t.type == 'DOT':
                if i + 1 < len(toks) and toks[i + 1].type in ('IDENTIFIER', 'BUILTIN'):
                    parts.append('.')       # dotted name: os.path
                else:
                    parts.append(' . ')     # relative: from . import x
            elif t.type == 'COMMA':
                parts.append(', ')
            else:
                if parts and parts[-1].endswith('.'):
                    parts.append(t.value)   # no space after a dot
                else:
                    parts.append(f' {t.value}')
        raw = re.sub(r'\s+', ' ', ''.join(parts)).strip()
        return ASTNode('IMPORT', value=raw)

    # ---------------------------------------------------------------- blocks
    def _parse_block(self) -> List[ASTNode]:
        nodes = []
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'NEWLINE':
                self.pos += 1
            elif tok.type == 'DEDENT':
                self.pos += 1
                break
            elif tok.type == 'INDENT':
                self.pos += 1
            else:
                nodes.append(self._parse_statement())
        return nodes

    def _skip_to_colon(self) -> None:
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'COLON':
                self.pos += 1
                return
            if tok.type == 'NEWLINE':
                self.pos += 1
                continue
            self.pos += 1  # stray tokens (e.g. `-> Int` annotations)

    # ------------------------------------------------------------- parameters
    def _parse_params(self) -> str:
        """Parse a parenthesised parameter/bases list and render it cleanly."""
        self.pos += 1  # LPAREN
        raw_parts = []
        depth = 1
        while self.pos < len(self.tokens) and depth:
            tok = self.tokens[self.pos]
            if tok.type == 'LPAREN':
                depth += 1
            elif tok.type == 'RPAREN':
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            elif tok.type == 'COMMA' and depth == 1:
                raw_parts.append(',')
            elif tok.type == 'NEWLINE':
                pass
            else:
                raw_parts.append(str(tok.value))
            self.pos += 1
        raw = ' '.join(raw_parts)
        raw = re.sub(r'\s*,\s*', ', ', raw.strip())
        raw = _PARAM_ANNOTATION.sub('', raw)
        raw = re.sub(r'\s*=\s*', '=', raw)
        raw = re.sub(r'\*\*\s*', '**', raw)
        raw = re.sub(r'\*\s*', '*', raw)
        raw = raw.strip().strip(',')
        return raw

    # ------------------------------------------------------------ expressions
    def _parse_expression(self, min_prec: int = 0) -> ASTNode:
        left = self._parse_unary()
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            op_type = _OP_TYPES.get(tok.type, tok.type)
            prec = _PRECEDENCE.get(op_type)
            if prec is None or prec < min_prec:
                break
            self.pos += 1
            right = self._parse_expression(prec + 1)
            op = _OP_TO_PY.get(op_type, op_type)
            left = ASTNode('EXPRESSION',
                           value=f'{self._node_to_str(left)} {op} {self._node_to_str(right)}')
        # ternary:  a if cond else b   (lowest precedence)
        if self._comp_depth == 0 and self.pos < len(self.tokens) and self.tokens[self.pos].type == 'IF':
            self.pos += 1
            cond = self._parse_expression()
            else_expr = ASTNode('IDENTIFIER', value='None')
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'ELSE':
                self.pos += 1
                else_expr = self._parse_expression()
            left = ASTNode('EXPRESSION',
                           value=f'{self._node_to_str(left)} if {self._node_to_str(cond)} else {self._node_to_str(else_expr)}')
        return left

    def _parse_unary(self) -> ASTNode:
        tok = self.tokens[self.pos]
        if tok.type == 'NOT':
            self.pos += 1
            operand = self._parse_unary()
            return ASTNode('EXPRESSION', value=f'not {self._node_to_str(operand)}')
        if tok.type in ('MINUS', '-') and tok.value == '-':
            self.pos += 1
            return ASTNode('EXPRESSION', value=f'-{self._node_to_str(self._parse_expression(_UNARY_BIND))}')
        if tok.type in ('PLUS', '+') and tok.value == '+':
            self.pos += 1
            return ASTNode('EXPRESSION', value=f'+{self._node_to_str(self._parse_expression(_UNARY_BIND))}')
        if tok.type == '~':
            self.pos += 1
            return ASTNode('EXPRESSION', value=f'~{self._node_to_str(self._parse_expression(_UNARY_BIND))}')
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self.tokens[self.pos]
        t = tok.type
        if t == 'NUMBER':
            self.pos += 1
            return ASTNode('NUMBER', value=tok.value)
        if t == 'BINARY_NUMBER':
            self.pos += 1
            return ASTNode('BINARY_NUMBER', value=tok.value)
        if t == 'STRING':
            self.pos += 1
            return self._parse_postfix(ASTNode('STRING', value=tok.value))
        if t in ('IDENTIFIER', 'BUILTIN'):
            name = tok.value
            self.pos += 1
            return self._parse_postfix(ASTNode('IDENTIFIER', value=name))
        if t in ('TRUE', 'FALSE', 'NONE'):
            self.pos += 1
            return ASTNode('IDENTIFIER', value={ 'TRUE': 'True', 'FALSE': 'False', 'NONE': 'None' }[t])
        if t == 'SELF':
            self.pos += 1
            return self._parse_postfix(ASTNode('IDENTIFIER', value='self'))
        if t == 'LPAREN':
            return self._parse_paren()
        if t == 'LBRACKET':
            return self._parse_list_literal()
        if t == 'LBRACE':
            return self._parse_dict_or_set()
        if t == 'LAMBDA':
            return self._parse_lambda()
        if t == 'BASH_START':
            return self._parse_bash_command()
        self.pos += 1
        return ASTNode('UNKNOWN', value=tok.value)

    def _parse_postfix(self, left: ASTNode) -> ASTNode:
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'DOT':
                self.pos += 1
                if self.pos < len(self.tokens) and self.tokens[self.pos].type in ('IDENTIFIER', 'BUILTIN'):
                    attr = self.tokens[self.pos].value
                    self.pos += 1
                    left = ASTNode('DOT', value=f'{self._node_to_str(left)}.{attr}')
                else:
                    break
            elif tok.type == 'LBRACKET':
                self.pos += 1
                left = self._parse_subscript(left)
            elif tok.type == 'LPAREN':
                self.pos += 1  # LPAREN
                receiver = self._node_to_str(left)
                args = self._parse_call_args()
                left = ASTNode('CALL', value=receiver, children=args)
            else:
                break
        return left

    def _parse_paren(self) -> ASTNode:
        self.pos += 1  # LPAREN
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RPAREN':
            self.pos += 1
            return ASTNode('TUPLE', value='()')
        first = self._parse_expression()
        self._skip_newlines()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
            items = [self._node_to_str(first)]
            while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                self.pos += 1
                self._skip_newlines()
                if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RPAREN':
                    break
                items.append(self._node_to_str(self._parse_expression()))
                self._skip_newlines()
            self._expect('RPAREN')
            return ASTNode('TUPLE', value=f'({", ".join(items)})')
        self._expect('RPAREN')
        return ASTNode('EXPRESSION', value=f'({self._node_to_str(first)})')

    def _parse_list_literal(self) -> ASTNode:
        self.pos += 1  # LBRACKET
        self._skip_newlines()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACKET':
            self.pos += 1
            return ASTNode('LIST', value='[]')
        first = self._parse_expression()
        self._skip_newlines()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type in ('FOR', 'IF'):
            comp = self._parse_comprehension_clauses(first)
            self._expect('RBRACKET')
            return ASTNode('LIST', value=f'[{comp}]')
        items = [self._node_to_str(first)]
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
            self.pos += 1
            self._skip_newlines()
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACKET':
                break
            items.append(self._node_to_str(self._parse_expression()))
            self._skip_newlines()
        self._expect('RBRACKET')
        return ASTNode('LIST', value=f'[{", ".join(items)}]')

    def _parse_dict_or_set(self) -> ASTNode:
        self.pos += 1  # LBRACE
        self._skip_newlines()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACE':
            self.pos += 1
            return ASTNode('DICT', value='{}')
        first = self._parse_expression()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COLON':
            self.pos += 1
            first_val = self._parse_expression()
            self._skip_newlines()
            if self.pos < len(self.tokens) and self.tokens[self.pos].type in ('FOR', 'IF'):
                pair = ASTNode('EXPRESSION', value=f'{self._node_to_str(first)}: {self._node_to_str(first_val)}')
                comp = self._parse_comprehension_clauses(pair)
                self._skip_newlines()
                self._expect('RBRACE')
                return ASTNode('DICT', value=f'{{{comp}}}')
            pairs = [f'{self._node_to_str(first)}: {self._node_to_str(first_val)}']
            while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
                self.pos += 1
                self._skip_newlines()
                if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACE':
                    break
                k = self._parse_expression()
                self._expect_token('COLON')
                v = self._parse_expression()
                pairs.append(f'{self._node_to_str(k)}: {self._node_to_str(v)}')
            self._expect('RBRACE')
            return ASTNode('DICT', value=f'{{{", ".join(pairs)}}}')
        items = [self._node_to_str(first)]
        self._skip_newlines()
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
            self.pos += 1
            self._skip_newlines()
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACE':
                break
            items.append(self._node_to_str(self._parse_expression()))
            self._skip_newlines()
        self._expect('RBRACE')
        return ASTNode('SET', value=f'{{{", ".join(items)}}}')

    def _parse_comprehension_clauses(self, body: ASTNode) -> str:
        parts = [self._node_to_str(body)]
        self._comp_depth += 1
        try:
            while self.pos < len(self.tokens):
                tok = self.tokens[self.pos]
                if tok.type == 'FOR':
                    self.pos += 1
                    var = self.tokens[self.pos].value
                    self.pos += 1
                    self._expect_token('IN')
                    it = self._parse_expression()
                    parts.append(f'for {var} in {self._node_to_str(it)}')
                elif tok.type == 'IF':
                    self.pos += 1
                    cond = self._parse_expression()
                    parts.append(f'if {self._node_to_str(cond)}')
                else:
                    break
        finally:
            self._comp_depth -= 1
        return ' '.join(parts)

    def _parse_subscript(self, left: ASTNode) -> ASTNode:
        # self.pos is just after LBRACKET
        items = []
        first = None
        if self.pos < len(self.tokens) and self.tokens[self.pos].type != 'COLON':
            first = self._parse_expression()
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COLON':
            self.pos += 1
            stop = None
            if self.pos < len(self.tokens) and self.tokens[self.pos].type not in ('RBRACKET', 'COLON', 'COMMA'):
                stop = self._parse_expression()
            step = None
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COLON':
                self.pos += 1
                if self.pos < len(self.tokens) and self.tokens[self.pos].type != 'RBRACKET':
                    step = self._parse_expression()
            items.append(self._render_slice(first, stop, step))
        else:
            if first is not None:
                items.append(self._node_to_str(first))
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'COMMA':
            self.pos += 1
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'RBRACKET':
                break
            items.append(self._node_to_str(self._parse_expression()))
        self._expect('RBRACKET')
        return ASTNode('INDEX', value=f'{self._node_to_str(left)}[{", ".join(items)}]')

    def _render_slice(self, start, stop, step) -> str:
        s = self._node_to_str(start) if start else ''
        if step:
            return f'{s}:{self._node_to_str(stop) if stop else ""}:{self._node_to_str(step)}'
        return f'{s}:{self._node_to_str(stop) if stop else ""}'

    def _parse_call_args(self) -> List[ASTNode]:
        # self.pos is just after LPAREN
        args = []
        while self.pos < len(self.tokens):
            self._skip_newlines()
            tok = self.tokens[self.pos]
            if tok.type == 'RPAREN':
                self.pos += 1
                break
            if tok.type == 'COMMA':
                self.pos += 1
                continue
            if tok.type == 'TIMES':
                self.pos += 1
                args.append(ASTNode('STAR', children=[self._parse_expression()]))
                continue
            if tok.type == 'POWER':
                self.pos += 1
                args.append(ASTNode('DSTAR', children=[self._parse_expression()]))
                continue
            arg = self._parse_expression()
            if self.pos < len(self.tokens) and self.tokens[self.pos].type == 'ASSIGN' and arg.type == 'IDENTIFIER':
                self.pos += 1
                val = self._parse_expression()
                args.append(ASTNode('KWARG', value=arg.value, children=[val]))
            else:
                args.append(arg)
        return args

    def _parse_lambda(self) -> ASTNode:
        self.pos += 1  # LAMBDA
        params = []
        while self.pos < len(self.tokens) and self.tokens[self.pos].type != 'COLON':
            tok = self.tokens[self.pos]
            if tok.type == 'COMMA':
                params.append(',')
            elif tok.type in ('NEWLINE', 'INDENT', 'DEDENT'):
                pass
            else:
                params.append(str(tok.value))
            self.pos += 1
        if self.pos < len(self.tokens):
            self.pos += 1  # COLON
        body = self._parse_expression()
        raw = ' '.join(params)
        raw = re.sub(r'\s*,\s*', ', ', raw.strip())
        raw = _PARAM_ANNOTATION.sub('', raw)
        raw = re.sub(r'\s*=\s*', '=', raw)
        raw = re.sub(r'\*\*\s*', '**', raw)
        raw = re.sub(r'\*\s*', '*', raw)
        return ASTNode('LAMBDA', value=raw.strip(), children=[body])

    def _parse_bash_command(self) -> ASTNode:
        parts = []
        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type == 'BASH_END':
                self.pos += 1
                break
            if tok.type in ('BASH_ARG', 'BASH_FLAG'):
                parts.append(ASTNode(tok.type, value=tok.value))
            self.pos += 1
        return ASTNode('BASH_COMMAND', children=parts)

    # ---------------------------------------------------------------- helpers
    def _expect(self, tok_type: str) -> None:
        if self.pos < len(self.tokens) and self.tokens[self.pos].type == tok_type:
            self.pos += 1
        # tolerate missing terminator (EOF etc.) — codegen will surface it

    def _skip_newlines(self) -> None:
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'NEWLINE':
            self.pos += 1

    def _expect_token(self, tok_type: str) -> None:
        self._expect(tok_type)

    def _node_to_str(self, node: ASTNode) -> str:
        if node is None:
            return 'None'
        t = node.type
        if t == 'NUMBER':
            return str(node.value)
        if t == 'BINARY_NUMBER':
            return f'int("{bin(node.value)[2:]}", 2)'
        if t == 'STRING':
            return node.value
        if t == 'IDENTIFIER':
            return node.value
        if t == 'EXPRESSION':
            return str(node.value)
        if t == 'CALL':
            args = ', '.join(self._node_to_str(c) for c in node.children)
            return f'{node.value}({args})'
        if t == 'KWARG':
            return f'{node.value}={self._node_to_str(node.children[0]) if node.children else "None"}'
        if t == 'STAR':
            return f'*{self._node_to_str(node.children[0]) if node.children else ""}'
        if t == 'DSTAR':
            return f'**{self._node_to_str(node.children[0]) if node.children else ""}'
        if t == 'LAMBDA':
            body = self._node_to_str(node.children[0]) if node.children else 'None'
            return f'lambda {node.value}: {body}'
        return str(node.value)
