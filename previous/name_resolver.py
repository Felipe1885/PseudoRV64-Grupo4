from __future__ import annotations

from ast_nodes import (
    Assignment,
    BinaryExpr,
    Block,
    CallExpr,
    CallStmt,
    Expr,
    IdentifierExpr,
    IfStmt,
    PrintStmt,
    Program,
    ReturnStmt,
    TypeName,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)
from symbols import FunctionSymbol, SymbolKind, Scope, Symbol
from semantic_errors import SemanticError, SemanticErrorKind, SemanticDiagnostic


class NameResolver:
    def __init__(self):
        self.diagnostics = []
        self.functions = {}
        self.scopes = []

    def resolve(self, program: Program) -> None:
        # 1. Colete todas as assinaturas de função.
        self.collect_functions(program)

        # 2. Valide a existência e a assinatura de main.
        self.validate_main(program)

        # 3/4. Percorra os corpos em ordem, criando um escopo para cada bloco e anotando declarações, usos e blocos na AST.
        for func in program.functions:
            parameters = {}
            for param in func.parameters:
                if param.name in parameters:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                            message=(
                                f"Declaração duplicada de '{param.name}'."
                            ),
                            span=param.span,
                        )
                    )
                    continue

                symbol = Symbol(
                    name=param.name,
                    kind=SymbolKind.PARAMETER,
                    type=param.type,
                    declaration=param,
                )
                parameters[param.name] = symbol
                param.metadata["symbol"] = symbol
            self.visit_block(func.body, None, parameters)

        # 5. Acumule os diagnósticos desta passagem antes de lançar SemanticError.
        if self.diagnostics:
            raise SemanticError(self.diagnostics)

    # Coleta as assinaturas de função
    def collect_functions(self, program: Program) -> None:
        for func in program.functions:
            # Verifica se a função já foi declarada, se sim, adiciona um diagnóstico de erro
            if func.name in self.functions:
                self.diagnostics.append(
                   SemanticDiagnostic(
                      kind=SemanticErrorKind.DUPLICATE_FUNCTION,
                      message=f"Função '{func.name}' já foi declarada.",
                      span=func.span,
                   )
                )
            # Se não foi, adiciona a função à tabela de símbolos
            else:
                param_types = tuple(param.type for param in func.parameters)
                symbol = FunctionSymbol (
                    name=func.name,
                    kind=SymbolKind.FUNCTION,
                    type=func.return_type,
                    declaration=func,
                    parameter_types=param_types,
                )
                self.functions[func.name] = symbol
                func.metadata["symbol"] = symbol


    # Valida a existência e a assinatura da main
    def validate_main(self, program: Program) -> None:
        main_sym = self.functions.get("main")
        # Main não existe
        if main_sym is None:
            self.diagnostics.append(
                SemanticDiagnostic(
                    kind=SemanticErrorKind.INVALID_MAIN,
                    message="Função 'main' ausente.",
                    span=program.span,
                )
            )
        # Main existe, mas não tem a assinatura correta
        elif main_sym.type != TypeName.INT or len(main_sym.parameter_types) != 0:
            self.diagnostics.append(
                SemanticDiagnostic(
                    kind=SemanticErrorKind.INVALID_MAIN,
                    message="Função 'main' deve ter assinatura 'int main()'.",
                    span=main_sym.declaration.span,
                )
            )
            
    def visit_block(self, block, parent, parameters=None):
        scope = Scope(parent=parent)
        self.scopes.append(scope)
        block.metadata["scope"] = scope

        if parameters:
            scope.symbols.update(parameters)

        for statement in block.statements:
            self.visit_statement(statement, scope)

    def visit_statement(self, statement, scope):
        if isinstance(statement, VarDecl):
            symbol = scope.symbols.get(statement.name)
            if symbol is not None:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                        message=f"Declaração duplicada de '{statement.name}'.",
                        span=statement.span,
                    )
                )
            else:
                symbol = Symbol(
                    name=statement.name,
                    kind=SymbolKind.VARIABLE,
                    type=statement.type,
                    declaration=statement,
                )
                scope.symbols[statement.name] = symbol
                statement.metadata["symbol"] = symbol

            if statement.initializer is not None:
                self.visit_expr(statement.initializer, scope)
            return

        if isinstance(statement, Assignment):
            self.visit_expr(statement.target, scope)
            self.visit_expr(statement.value, scope)
            return

        if isinstance(statement, CallStmt):
            self.visit_expr(statement.call, scope)
            return

        if isinstance(statement, IfStmt):
            self.visit_expr(statement.condition, scope)
            self.visit_block(statement.then_block, scope)
            if statement.else_block is not None:
                self.visit_block(statement.else_block, scope)
            return

        if isinstance(statement, WhileStmt):
            self.visit_expr(statement.condition, scope)
            self.visit_block(statement.body, scope)
            return

        if isinstance(statement, ReturnStmt):
            if statement.value is not None:
                self.visit_expr(statement.value, scope)
            return

        if isinstance(statement, PrintStmt):
            for item in statement.items:
                if isinstance(item, Expr):
                    self.visit_expr(item, scope)
            return

        if isinstance(statement, Block):
            self.visit_block(statement, scope)

    def visit_expr(self, expression, scope):
        if isinstance(expression, IdentifierExpr):
            symbol = self.lookup_variable(expression.name, scope)
            if symbol is None:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.UNDECLARED_VARIABLE,
                        message=f"Variável '{expression.name}' não foi declarada.",
                        span=expression.span,
                    )
                )
            else:
                expression.metadata["symbol"] = symbol
            return

        if isinstance(expression, CallExpr):
            symbol = self.functions.get(expression.name)
            if symbol is None:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.UNDECLARED_FUNCTION,
                        message=f"Função '{expression.name}' não foi declarada.",
                        span=expression.span,
                    )
                )
            else:
                expression.metadata["symbol"] = symbol

            for argument in expression.arguments:
                self.visit_expr(argument, scope)
            return

        if isinstance(expression, BinaryExpr):
            self.visit_expr(expression.left, scope)
            self.visit_expr(expression.right, scope)
            return

        if isinstance(expression, UnaryExpr):
            self.visit_expr(expression.operand, scope)

    def lookup_variable(self, name, scope):
        current = scope
        while current is not None:
            symbol = current.symbols.get(name)
            if symbol is not None:
                return symbol
            current = current.parent
        return None


"""Construa escopos, símbolos e vínculos entre usos e declarações."""
def resolve_names(program: Program) -> None:
    resolver = NameResolver()
    resolver.resolve(program)
