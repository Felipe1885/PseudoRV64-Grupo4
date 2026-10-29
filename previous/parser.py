from __future__ import annotations

from collections.abc import Sequence

from Lexer import Token, TokenKind
from ast_nodes import (
    Assignment,
    BinaryExpr,
    BinaryOperator,
    Block,
    BoolLiteral,
    CallExpr,
    CallStmt,
    Expr,
    FunctionDecl,
    IdentifierExpr,
    IfStmt,
    IntLiteral,
    Node,
    Parameter,
    PrintItem,
    PrintStmt,
    Program,
    ReturnStmt,
    SourceSpan,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    UnaryOperator,
    VarDecl,
    WhileStmt,
)


TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_FALSE,
    TokenKind.KW_TRUE,
    TokenKind.LEFT_PAREN,
    TokenKind.LOGICAL_NOT,
    TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER,
    TokenKind.KW_IF,
    TokenKind.KW_WHILE,
    TokenKind.KW_RETURN,
    TokenKind.KW_PRINT,
    TokenKind.LEFT_BRACE,
}


TYPE_BY_TOKEN = {
    TokenKind.KW_INT: TypeName.INT,
    TokenKind.KW_BOOL: TypeName.BOOL,
    TokenKind.KW_VOID: TypeName.VOID,
}


class ParserError(Exception):
    def __init__(self, token: Token, expected: set[TokenKind]):
        self.token = token
        self.expected = frozenset(expected)
        super().__init__()

    @property
    def line(self) -> int:
        return self.token.line

    @property
    def column(self) -> int:
        return self.token.column

    def __str__(self) -> str:
        names = ", ".join(kind.name for kind in sorted(
            self.expected,
            key=lambda kind: kind.value,
        ))
        return (
            f"erro sintático em {self.line}:{self.column}: esperado {{{names}}}, "
            f"encontrado {self.token.kind.name} ({self.token.lexeme!r})"
        )


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        if not self.tokens:
            raise ValueError("a sequência de tokens deve terminar em EOF")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("o último token deve ser EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF deve aparecer uma única vez, no final")
        self.current = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def check(self, kind: TokenKind) -> bool:
        return self.peek().kind is kind

    def advance(self) -> Token:
        token = self.peek()
        if self.current < len(self.tokens) - 1:
            self.current += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kinds: TokenKind | set[TokenKind]) -> Token:
        expected = kinds if isinstance(kinds, set) else {kinds}
        token = self.peek()
        if token.kind not in expected:
            raise ParserError(token, set(expected))
        return self.advance()

    @staticmethod
    def _token_span(token: Token) -> SourceSpan:
        return SourceSpan(
            token.line,
            token.column,
            token.line,
            token.column + len(token.lexeme),
        )

    @staticmethod
    def _start(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.start_line, value.span.start_column
        return value.line, value.column

    @staticmethod
    def _end(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.end_line, value.span.end_column
        return value.line, value.column + len(value.lexeme)

    @classmethod
    def _span(cls, first: Token | Node, last: Token | Node) -> SourceSpan:
        start_line, start_column = cls._start(first)
        end_line, end_column = cls._end(last)
        return SourceSpan(start_line, start_column, end_line, end_column)

    def parse(self) -> Program:
        return self.parse_program()

    # program ::= function* EOF
    def parse_program(self) -> Program:
        start = self.peek()
        functions: list[FunctionDecl] = []
        while self.peek().kind in TYPE_START:
            functions.append(self.parse_function())
        eof = self.expect(TokenKind.EOF)
        return Program(functions, span=self._span(start, eof))

    # function ::= type IDENTIFIER ... block
    def parse_function(self) -> FunctionDecl:
        start = self.peek()
        return_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        self.expect(TokenKind.LEFT_PAREN)
        parameters = (
            self.parse_parameter_list()
            if self.peek().kind in TYPE_START
            else []
        )
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return FunctionDecl(
            return_type,
            name.lexeme,
            parameters,
            body,
            span=self._span(start, body),
        )

    # type ::= KW_INT | KW_BOOL | KW_VOID
    def parse_type(self) -> TypeName:
        token = self.expect(TYPE_START)
        return TYPE_BY_TOKEN[token.kind]

    def parse_parameter_list(self) -> list[Parameter]:
        parameters: list[Parameter] = [self.parse_parameter()]

        while self.match(TokenKind.COMMA):
                parameters.append(self.parse_parameter())

        return parameters
        
    def parse_parameter(self) -> Parameter:
        start = self.peek()
        param_type = self.parse_type()
        name_token = self.expect(TokenKind.IDENTIFIER)
        return Parameter(
            type = param_type, 
            name = name_token.lexeme, 
            span = self._span(start, name_token)
        )
        
    def parse_block(self) -> Block:
        start = self.expect(TokenKind.LEFT_BRACE)
        statements: list[Stmt] = []
        while self.peek().kind in STATEMENT_START:
            statements.append(self.parse_statement())

        end = self.expect(TokenKind.RIGHT_BRACE)
        return Block(statements, span=self._span(start, end))
        
    def parse_statement(self) -> Stmt:
        kind = self.peek().kind
        if kind in TYPE_START:
            return self.parse_declaration()
        if kind is TokenKind.IDENTIFIER:
            return self.parse_id_or_call_statement()
        if kind is TokenKind.KW_IF:
            return self.parse_if_statement()
        if kind is TokenKind.KW_WHILE:
            return self.parse_while_statement()
        if kind is TokenKind.KW_RETURN:
            return self.parse_return_statement()
        if kind is TokenKind.KW_PRINT:
            return self.parse_print_statement()
        if kind is TokenKind.LEFT_BRACE:
            return self.parse_block()

        raise ParserError(self.peek(), STATEMENT_START)

    def parse_id_or_call_statement(self) -> Stmt:
        start = self.expect(TokenKind.IDENTIFIER)
        if self.match(TokenKind.LEFT_PAREN):
            arguments = self.parse_arguments()
            rparen = self.expect(TokenKind.RIGHT_PAREN)
            end = self.expect(TokenKind.SEMICOLON)
            call = CallExpr(
                name=start.lexeme,
                arguments=arguments,
                span=self._span(start, rparen),
            )
            return CallStmt(call=call, span=self._span(start, end))
        if self.match(TokenKind.ASSIGN):
            expression = self.parse_expression()
            end = self.expect(TokenKind.SEMICOLON)
            target = IdentifierExpr(name=start.lexeme, span=self._token_span(start))
            return Assignment(
                target=target,
                value=expression,
                span=self._span(start, end)
            )
        raise ParserError(self.peek(), {TokenKind.LEFT_PAREN, TokenKind.ASSIGN})  

    def parse_declaration(self) -> Stmt:
        start = self.peek()
        type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        expression = None
        if self.match(TokenKind.ASSIGN):
            expression = self.parse_expression()
        end = self.expect(TokenKind.SEMICOLON)
        return VarDecl(
            type=type,
            name=name.lexeme,
            initializer=expression,
            span=self._span(start, end)
        )

    def parse_if_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_IF)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        then_block = self.parse_block()
        else_block = None
        if (self.match(TokenKind.KW_ELSE)):
            else_block = self.parse_block()
        return IfStmt(condition, then_block, else_block, span=self._span(start, else_block or then_block))
        
    def parse_while_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_WHILE)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return WhileStmt(condition, body, span=self._span(start, body))
        
    def parse_return_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_RETURN)

        value = None
        if self.peek().kind in EXPRESSION_START:
            value = self.parse_expression()

        end = self.expect(TokenKind.SEMICOLON)
        return ReturnStmt(value, span=self._span(start, end))

    def parse_print_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_PRINT)
        self.expect(TokenKind.LEFT_PAREN)

        items: list[PrintItem] = []
        first_item = self.parse_print_item()
        if not first_item:
            raise ParserError(self.peek(), {TokenKind.STRING_LITERAL, TokenKind.IDENTIFIER})
        items.append(first_item)
        while self.match(TokenKind.COMMA):
            items.append(self.parse_print_item())

        self.expect(TokenKind.RIGHT_PAREN)
        end = self.expect(TokenKind.SEMICOLON)

        return PrintStmt(items=items, span=self._span(start, end))
        
    def parse_print_item(self) -> PrintItem:
        if self.check(TokenKind.STRING_LITERAL):
            return self.parse_string_literals()
        return self.parse_expression()
        
    def parse_string_literals(self) -> StringLiteral:
        first_token = self.expect(TokenKind.STRING_LITERAL)
        last_token = first_token
        
        combined_value = str(first_token.value)

        while self.check(TokenKind.STRING_LITERAL):
            token = self.advance()
            combined_value += str(token.value)
            last_token = token

        return StringLiteral(
            value=combined_value,
            span=self._span(first_token, last_token),
        )
        
    def parse_expression(self) -> Expr:
        return self.parse_logical_or()
        
    def parse_logical_or(self) -> Expr:
        left = self.parse_logical_and()

        while self.match(TokenKind.LOGICAL_OR):
            right = self.parse_logical_and()
            left = BinaryExpr(
                operator=BinaryOperator.LOGICAL_OR,
                left=left,
                right=right,
                span=self._span(left, right)
            )

        return left
        
    def parse_logical_and(self) -> Expr:
        left = self.parse_equality()
        
        while self.match(TokenKind.LOGICAL_AND):
            right = self.parse_equality()
            left = BinaryExpr(
                operator=BinaryOperator.LOGICAL_AND,
                left=left,
                right=right,
                span=self._span(left, right)
            )
        return left
        
    def parse_equality(self) -> Expr:
        left = self.parse_relational()

        while True:
            if self.match(TokenKind.EQUAL_EQUAL):
                operator = BinaryOperator.EQUAL
            elif self.match(TokenKind.NOT_EQUAL):
                operator = BinaryOperator.NOT_EQUAL
            else:
                break

            right = self.parse_relational()
            left = BinaryExpr(
                operator=operator,
                left=left,
                right=right,
                span=self._span(left, right),
            )

        return left
        
    def parse_relational(self) -> Expr:
        left = self.parse_additive()

        while True:
            if self.match(TokenKind.LESS):
                operator = BinaryOperator.LESS
            elif self.match(TokenKind.LESS_EQUAL):
                operator = BinaryOperator.LESS_EQUAL
            elif self.match(TokenKind.GREATER):
                operator = BinaryOperator.GREATER
            elif self.match(TokenKind.GREATER_EQUAL):
                operator = BinaryOperator.GREATER_EQUAL
            else:
                break

            right = self.parse_additive()
            left = BinaryExpr(
                operator=operator,
                left=left,
                right=right,
                span=self._span(left, right),
            )

        return left
        
    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()

        while True:
            if self.match(TokenKind.PLUS):
                operator = BinaryOperator.ADD
            elif self.match(TokenKind.MINUS):
                operator = BinaryOperator.SUBTRACT
            else:
                break

            right = self.parse_multiplicative()
            left = BinaryExpr(
                operator=operator,
                left=left,
                right=right,
                span=self._span(left, right),
            )

        return left
        
    def parse_multiplicative(self) -> Expr:
        left = self.parse_unary()

        while True:
            if self.match(TokenKind.STAR):
                operator = BinaryOperator.MULTIPLY
            elif self.match(TokenKind.SLASH):
                operator = BinaryOperator.DIVIDE
            elif self.match(TokenKind.PERCENT):
                operator = BinaryOperator.REMAINDER
            else:
                break

            right = self.parse_unary()
            left = BinaryExpr(
                operator=operator,
                left=left,
                right=right,
                span=self._span(left, right),
            )

        return left
        
    def parse_unary(self) -> Expr:
        start = self.peek()

        if self.match(TokenKind.LOGICAL_NOT):
            operand = self.parse_unary()
            return UnaryExpr(
                operator=UnaryOperator.NOT,
                operand=operand,
                span=self._span(start, operand),
            )

        if self.match(TokenKind.MINUS):
            operand = self.parse_unary()
            return UnaryExpr(
                operator=UnaryOperator.NEGATE,
                operand=operand,
                span=self._span(start, operand),
            )

        return self.parse_primary()
        
    def parse_primary(self) -> Expr:
        start = self.peek()
        if (self.match(TokenKind.KW_TRUE)):
            return BoolLiteral(value=True, span=self._token_span(start))
        if (self.match(TokenKind.KW_FALSE)):
            return BoolLiteral(value=False, span=self._token_span(start))
        if (self.match(TokenKind.INT_LITERAL)):
            return IntLiteral(value=int(start.lexeme), span=self._token_span(start))
        if (self.match(TokenKind.LEFT_PAREN)):
            expression = self.parse_expression()
            self.expect(TokenKind.RIGHT_PAREN)
            return Expr(value=expression, span=self._span(start, expression))
        if (self.match(TokenKind.IDENTIFIER)):
            if self.match(TokenKind.LEFT_PAREN):
                arguments = self.parse_arguments()
                end = self.expect(TokenKind.RIGHT_PAREN)
                return CallExpr(name=start.lexeme, arguments=arguments, span=self._span(start, end))
            else:
                return IdentifierExpr(name=start.lexeme, span=self._token_span(start))

    def parse_arguments(self) -> list[Expr]:
        arguments: list[Expr] = []

        if self.peek().kind in EXPRESSION_START:
            arguments.append(self.parse_expression())
            while self.match(TokenKind.COMMA):
                argument = self.parse_expression()
                if not argument:
                    raise ParserError(self.peek(), EXPRESSION_START)
                arguments.append(argument)
                
        return arguments
