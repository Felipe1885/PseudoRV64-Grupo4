from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterator


class TokenKind(enum.Enum):
    """Classe já implementada: nomes e números não devem ser alterados."""

    EOF = -1

    IDENTIFIER = 1
    INT_LITERAL = 2
    STRING_LITERAL = 3

    KW_INT = 10
    KW_BOOL = 11
    KW_VOID = 12
    KW_TRUE = 13
    KW_FALSE = 14
    KW_IF = 15
    KW_ELSE = 16
    KW_WHILE = 17
    KW_RETURN = 18
    KW_PRINT = 19

    PLUS = 20
    MINUS = 21
    STAR = 22
    SLASH = 23
    PERCENT = 24
    LESS = 25
    LESS_EQUAL = 26
    GREATER = 27
    GREATER_EQUAL = 28
    EQUAL_EQUAL = 29
    NOT_EQUAL = 30
    LOGICAL_AND = 31
    LOGICAL_OR = 32
    LOGICAL_NOT = 33
    ASSIGN = 34

    LEFT_PAREN = 40
    RIGHT_PAREN = 41
    LEFT_BRACE = 42
    RIGHT_BRACE = 43
    COMMA = 44
    SEMICOLON = 45


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    value: int | str | bool | None
    line: int
    column: int

    def __str__(self) -> str:
        return (
            f"<{self.kind.value}, {self.kind.name}, {self.lexeme!r}, "
            f"{self.value!r}, {self.line}, {self.column}>"
        )


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"erro léxico em {self.line}:{self.column}: {self.message}"


class Lexer:
    """Converte texto-fonte MicroC em uma sequência de tokens."""

    def __init__(self, source: str):
        self.source = source

    def tokens(self) -> Iterator[Token]:
        """Produza todos os tokens significativos e um único EOF ao final."""
        tokens = []
        current_lexeme = ""
        line = 1
        column = 1
        
        i = 0
        while i < len(self.source):
            char = self.source[i]
            #print("i: " + str(i) + "repr" + repr(char))
            if char.isspace(): # Ignorar espaços em branco
                column += 1
                if char == '\n':
                    line += 1
                    column = 1
                i += 1
            elif char in ['(', ')', '{', '}', ',', ';', '+', '-', '*', '%']: # Tokens de um caractere
                if char == '(':
                    yield Token(TokenKind.LEFT_PAREN, char, None, line, column)
                elif char == ')':
                    yield Token(TokenKind.RIGHT_PAREN, char, None, line, column)
                elif char == '{':
                    yield Token(TokenKind.LEFT_BRACE, char, None, line, column)
                elif char == '}':
                    yield Token(TokenKind.RIGHT_BRACE, char, None, line, column)
                elif char == ',':
                    yield Token(TokenKind.COMMA, char, None, line, column)
                elif char == ';':
                    yield Token(TokenKind.SEMICOLON, char, None, line, column)
                elif char == '+':
                    yield Token(TokenKind.PLUS, char, None, line, column)
                elif char == '-':
                    yield Token(TokenKind.MINUS, char, None, line, column)
                elif char == '*':
                    yield Token(TokenKind.STAR, char, None, line, column)
                elif char == '%':
                    yield Token(TokenKind.PERCENT, char, None, line, column)
                i += 1
                column += 1
            elif char.isdigit(): # Literais inteiros
                while i < len(self.source) and self.source[i].isdigit():
                    current_lexeme += self.source[i]
                    i += 1
                yield Token(TokenKind.INT_LITERAL, current_lexeme, int(current_lexeme), line, column)
                column += len(current_lexeme)
            elif char == '"': # Literais de string
                i += 1
                while i < len(self.source) and (self.source[i] != '"' or (self.source[i] == '"' and self.source[i - 1] == '\\')):
                    if (self.source[i] == '\n'):
                         raise LexerError("string literal não pode conter quebras de linha", line, column+len(current_lexeme)+1)
                    if (self.source[i] not in ['n', 't', '\"', '\\'] and self.source[i - 1] == '\\'):
                        raise LexerError("string possui barra invertida", line, column+len(current_lexeme))
                    if (self.source[i] == '\\' and self.source[i - 1] == '\\'):
                        current_lexeme += self.source[i]
                        i += 1
                    current_lexeme += self.source[i]
                    i += 1
                if (i == len(self.source)):
                    raise LexerError("string literal não termina com aspas", line, column)
                if i < len(self.source) and self.source[i] == '"':
                    value = current_lexeme.encode().decode('unicode_escape')
                    yield Token(TokenKind.STRING_LITERAL, f'"{current_lexeme}"', value, line, column)
                i += 1
                column += len(current_lexeme) + 1
            elif (char.isalpha() and char.isascii()) or char == '_': # Identificadores ou keywords
                while i < len(self.source) and (self.source[i].isalnum() or self.source[i] == '_'):
                    current_lexeme += self.source[i]
                    i += 1
                if current_lexeme in ['int', 'bool', 'void', 'if', 'else', 'while', 'return', 'print']:
                    yield Token(TokenKind[f'KW_{current_lexeme.upper()}'], current_lexeme, None, line, column)
                elif current_lexeme in ['true']:
                    yield Token(TokenKind[f'KW_{current_lexeme.upper()}'], current_lexeme, True, line, column)
                elif current_lexeme in ['false']:
                    yield Token(TokenKind[f'KW_{current_lexeme.upper()}'], current_lexeme, False, line, column)
                else:
                    yield Token(TokenKind.IDENTIFIER, current_lexeme, current_lexeme, line, column)
                column += len(current_lexeme)
            elif char in ['<', '>', '=', '!', '&', '|']: # Operadores compostos
                if i + 1 < len(self.source):
                    next_char = self.source[i + 1]
                    if char == '<' and next_char == '=':
                        yield Token(TokenKind.LESS_EQUAL, '<=', None, line, column)
                        i += 1
                        column += 1
                    elif char == '>' and next_char == '=':
                        yield Token(TokenKind.GREATER_EQUAL, '>=', None, line, column)
                        i += 1
                        column += 1
                    elif char == '=' and next_char == '=':
                        yield Token(TokenKind.EQUAL_EQUAL, '==', None, line, column)
                        i += 1
                        column += 1
                    elif char == '!' and next_char == '=':
                        yield Token(TokenKind.NOT_EQUAL, '!=', None, line, column)
                        i += 1
                        column += 1
                    elif char == '&' and next_char == '&':
                        yield Token(TokenKind.LOGICAL_AND, '&&', None, line, column)
                        i += 1
                        column += 1
                    elif char == '|' and next_char == '|':
                        yield Token(TokenKind.LOGICAL_OR, '||', None, line, column)
                        i += 1
                        column += 1
                    else:
                        if char == '<':
                            yield Token(TokenKind.LESS, '<', None, line, column)
                        elif char == '>':
                            yield Token(TokenKind.GREATER, '>', None, line, column)
                        elif char == '=':
                            yield Token(TokenKind.ASSIGN, '=', None, line, column)
                        elif char == '!':
                            yield Token(TokenKind.LOGICAL_NOT, '!', None, line, column)
                        elif char == '&':
                            raise LexerError("operador '&' não é válido sozinho", line, column)
                        elif char == '|':
                            raise LexerError("operador '|' não é válido sozinho", line, column)
                else:
                    if char == '<':
                        yield Token(TokenKind.LESS, '<', None, line, column)
                    elif char == '>':
                        yield Token(TokenKind.GREATER, '>', None, line, column)
                    elif char == '=':
                        yield Token(TokenKind.ASSIGN, '=', None, line, column)
                    elif char == '!':
                        yield Token(TokenKind.LOGICAL_NOT, '!', None, line, column)
                    elif char == '&':
                        raise LexerError("operador '&' não é válido sozinho", line, column)
                    elif char == '|':
                        raise LexerError("operador '|' não é válido sozinho", line, column)
                i += 1
                column += 1
            elif char == '/': # Comentários ou operador de divisão
                if i + 1 < len(self.source):
                    next_char = self.source[i + 1]
                    if next_char == '/': # Comentário de linha
                        while i < len(self.source) and self.source[i] != '\n':
                            i += 1
                            column += 1
                    elif next_char == '*': # Comentário de bloco
                        ini_line = line
                        ini_column = column
                        i += 2
                        column += 2
                        while i + 1 < len(self.source) and not (self.source[i] == '*' and self.source[i + 1] == '/'):
                            if (self.source[i] == '\n'):
                                line += 1
                                column = 0
                            i += 1
                            column += 1
                        if i + 1 < len(self.source):
                            i += 2
                            column += 2
                        else:
                            raise LexerError("comentário de bloco não termina", ini_line, ini_column)
                    else:
                        yield Token(TokenKind.SLASH, '/', None, line, column)
                        i += 1
                        column += 1
                else:
                    yield Token(TokenKind.SLASH, '/', None, line, column)
                    column += 1
            else:
                raise LexerError(f"caractere inesperado {char}", line, column)

            current_lexeme = ""

        yield Token(TokenKind.EOF, "", None, line, column)

    def scan(self) -> list[Token]:
        return list(self.tokens())

