"""Lexer for Externum v3 — tokenizes the full language.

Token kinds:
  - structural: NEWLINE, INDENT, DEDENT
  - literals:   NUMBER, BINARY_NUMBER, STRING, IDENTIFIER
  - builtins:   BUILTIN (print, input, len, ...)
  - keywords:   IF ELSE ELIF FOR WHILE DEF CLASS RETURN YIELD IMPORT FROM AS
                PASS BREAK CONTINUE TRY EXCEPT FINALLY RAISE WITH ASSERT DEL
                GLOBAL NONLOCAL LAMBDA AND OR NOT IN IS TRUE FALSE NONE SELF
  - operators:  ** == != <= >= << >> && || += -= *= /= // + - * / % = < > ~ & | ^
                ( ) [ ] { } , : . ; -> @
  - bash:       BASH_START, BASH_ARG, BASH_FLAG, BASH_END, BASH_BLOCK
"""

import re
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class Token:
    type: str
    value: any
    pos: Tuple[int, int]

class Lexer:
    PYTHON_KEYWORDS = {
        'if', 'else', 'elif', 'for', 'while', 'def', 'class',
        'return', 'yield', 'import', 'from', 'as', 'pass', 'break',
        'continue', 'try', 'except', 'finally', 'raise', 'with',
        'assert', 'del', 'global', 'nonlocal', 'lambda',
        'True', 'False', 'None', 'self', 'and', 'or', 'not', 'in', 'is'
    }

    BUILTINS = {'print', 'input', 'len', 'str', 'int', 'float', 'bool',
                'list', 'dict', 'tuple', 'set', 'range', 'open', 'type',
                'sum', 'min', 'max', 'abs', 'round', 'enumerate', 'zip',
                'sorted', 'reversed', 'chr', 'ord', 'hex', 'oct', 'bin',
                'isinstance', 'repr', 'id', 'hash', 'format'}

    # Ordered: longest/most specific first so greedy matching works.
    OPERATORS = ['**', '<<', '>>', '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=',
                 '//', '&&', '||', '->', '+', '-', '*', '/', '%', '=', '<', '>',
                 '~', '&', '|', '^', '(', ')', '[', ']', '{', '}', ',', ':', '.', ';', '@']

    NAME_MAP = {
        '(': 'LPAREN', ')': 'RPAREN', ',': 'COMMA', ':': 'COLON', ';': 'SEMICOLON',
        '.': 'DOT', '[': 'LBRACKET', ']': 'RBRACKET', '{': 'LBRACE', '}': 'RBRACE',
        '+': 'PLUS', '-': 'MINUS', '*': 'TIMES', '/': 'DIVIDE', '**': 'POWER', '%': 'MOD',
        '=': 'ASSIGN',
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []
        self.indent_stack = [0]
        self._at_line_start = True
        self.bracket_depth = 0

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self._tokenize_line()
        return self.tokens

    # ------------------------------------------------------------------ main
    def _tokenize_line(self):
        if self.pos >= len(self.source):
            return

        if self._at_line_start and self.bracket_depth == 0:
            self._at_line_start = False
            # Blank and comment-only lines never affect indentation.
            line_end = self.source.find('\n', self.pos)
            if line_end == -1:
                line_end = len(self.source)
            line_content = self.source[self.pos:line_end].strip()
            if line_content == '' or line_content.startswith('#'):
                while self.pos < len(self.source) and self.source[self.pos] == ' ':
                    self.pos += 1
            else:
                indent = self._consume_indent()
                if indent > self.indent_stack[-1]:
                    self.tokens.append(Token('INDENT', indent, (self.line, self.col)))
                    self.indent_stack.append(indent)
                elif indent < self.indent_stack[-1]:
                    while self.indent_stack and indent < self.indent_stack[-1]:
                        self.indent_stack.pop()
                        self.tokens.append(Token('DEDENT', 0, (self.line, self.col)))
        elif self._at_line_start:
            self._at_line_start = False
            while self.pos < len(self.source) and self.source[self.pos] == ' ':
                self.pos += 1

        if self.pos >= len(self.source):
            return

        char = self.source[self.pos]

        if char == '\n':
            self.tokens.append(Token('NEWLINE', '\n', (self.line, self.col)))
            self.line += 1
            self.col = 1
            self.pos += 1
            self._at_line_start = True
            return

        if char == '#':
            end = self.source.find('\n', self.pos)
            if end == -1:
                end = len(self.source)
            self.pos = end
            return

        if char == ' ':
            self.pos += 1
            return

        if char == '`':
            return self._tokenize_bash_inline()

        if self.source[self.pos:self.pos + 2] == '%%':
            return self._tokenize_bash_block()

        op = self._try_match_operator()
        if op:
            self.tokens.append(Token(op[0], op[1], (self.line, self.col)))
            self.pos += len(op[1])
            if op[1] in ('(', '[', '{'):
                self.bracket_depth += 1
            elif op[1] in (')', ']', '}') and self.bracket_depth > 0:
                self.bracket_depth -= 1
            return

        # triple-quoted strings first (multiline)
        if self.source[self.pos:self.pos + 3] in ('"""', "'''"):
            return self._tokenize_triple_string()

        # prefixed strings: f"..." r"..." b"..."
        if m := re.match(r'[fFrRbBuU]"(?:[^"\\]|\\.)*"', self.source[self.pos:]):
            self.tokens.append(Token('STRING', m.group(0), (self.line, self.col)))
            self.pos += len(m.group(0))
            return
        if m := re.match(r"[fFrRbBuU]'(?:[^'\\]|\\.)*'", self.source[self.pos:]):
            self.tokens.append(Token('STRING', m.group(0), (self.line, self.col)))
            self.pos += len(m.group(0))
            return

        if m := re.match(r'"(?:[^"\\]|\\.)*"', self.source[self.pos:]):
            self.tokens.append(Token('STRING', m.group(0), (self.line, self.col)))
            self.pos += len(m.group(0))
            return

        if m := re.match(r"'", self.source[self.pos:]):
            end = self.source.find("'", self.pos + 1)
            if end == -1:
                end = len(self.source) - 1
            self.tokens.append(Token('STRING', self.source[self.pos:end + 1], (self.line, self.col)))
            self.pos = end + 1
            return

        if m := re.match(r'0b[01]+', self.source[self.pos:]):
            value = int(m.group(0), 2)
            self.tokens.append(Token('BINARY_NUMBER', value, (self.line, self.col)))
            self.pos += len(m.group(0))
            return

        if m := re.match(r'0x[0-9a-fA-F]+', self.source[self.pos:]):
            value = int(m.group(0), 16)
            self.tokens.append(Token('NUMBER', value, (self.line, self.col)))
            self.pos += len(m.group(0))
            return

        if m := re.match(r'\d+(\.\d+)?', self.source[self.pos:]):
            val = m.group(0)
            value = float(val) if '.' in val else int(val)
            self.tokens.append(Token('NUMBER', value, (self.line, self.col)))
            self.pos += len(val)
            return

        if m := re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', self.source[self.pos:]):
            value = m.group(0)
            if value in self.PYTHON_KEYWORDS:
                self.tokens.append(Token(value.upper(), value, (self.line, self.col)))
            elif value in self.BUILTINS:
                self.tokens.append(Token('BUILTIN', value, (self.line, self.col)))
            else:
                self.tokens.append(Token('IDENTIFIER', value, (self.line, self.col)))
            self.pos += len(value)
            return

        raise SyntaxError(f"Unexpected '{char}' at {self.line}:{self.col}")

    # -------------------------------------------------------------- helpers
    def _consume_indent(self) -> int:
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] == ' ':
            self.pos += 1
        return self.pos - start

    def _try_match_operator(self):
        for op in self.OPERATORS:
            if self.source[self.pos:self.pos + len(op)] == op:
                return (self.NAME_MAP.get(op, op), op)
        return None

    def _tokenize_bash_inline(self):
        end = self.source.find('`', self.pos + 1)
        if end == -1:
            end = len(self.source)
        content = self.source[self.pos + 1:end]
        self.tokens.append(Token('BASH_START', 'BASH_START', (self.line, self.col)))
        for part in content.split():
            if part.startswith('-'):
                self.tokens.append(Token('BASH_FLAG', part, (self.line, self.col)))
            else:
                self.tokens.append(Token('BASH_ARG', part, (self.line, self.col)))
        self.tokens.append(Token('BASH_END', 'BASH_END', (self.line, self.col)))
        self.pos = end + 1

    def _tokenize_bash_block(self):
        end = self.source.find('%%', self.pos + 2)
        if end == -1:
            end = len(self.source)
        content = self.source[self.pos + 2:end].strip()
        self.tokens.append(Token('BASH_BLOCK', content, (self.line, self.col)))
        self.pos = end + 2

    def _tokenize_triple_string(self):
        quote = self.source[self.pos:self.pos + 3]
        end = self.source.find(quote, self.pos + 3)
        if end == -1:
            end = len(self.source)
        raw = self.source[self.pos:end + 3]
        self.tokens.append(Token('STRING', raw, (self.line, self.col)))
        # advance line/col across newlines inside the literal
        self.pos = end + 3
        self.line += raw.count('\n')
        self.col = len(raw) - raw.rfind('\n')
        self._at_line_start = False
