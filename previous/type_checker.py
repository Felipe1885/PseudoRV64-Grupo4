from __future__ import annotations

from ast_nodes import CallExpr, Program, TypeName, VarDecl, IdentifierExpr, IntLiteral, BoolLiteral, Assignment, BinaryExpr, BinaryOperator, UnaryExpr, UnaryOperator, ReturnStmt, IfStmt, WhileStmt, CallStmt, Block, PrintStmt, Expr
from semantic_errors import SemanticError, SemanticErrorKind, SemanticDiagnostic

class TypeChecker:
    def __init__(self):
        self.diagnostics = []

    def check(self, program: Program) -> None:
        for func in program.functions:
            self.current_function = func
            for param in func.parameters:
                if param.type == TypeName.VOID:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.VOID_PARAMETER,
                            message=f"Parâmetro '{param.name}' não pode ser do tipo 'void'.",
                            span=param.span,
                        )
                    )
            self.visit_block(func.body)

    def visit_block(self, block):
        for stmt in block.statements:
            self.visit_statement(stmt)

    def visit_statement(self, stmt):
        if isinstance(stmt, VarDecl):
            if stmt.type == TypeName.VOID:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.VOID_VARIABLE,
                        message=f"Variável '{stmt.name}' não pode ser declarada com tipo 'void'.",
                        span=stmt.span,
                    )
                )
            elif stmt.initializer is not None:
                initializer_type = self.visit_expr(stmt.initializer)
                if initializer_type is not None:
                    if initializer_type == TypeName.VOID:
                        self.diagnostics.append(
                            SemanticDiagnostic(
                                kind=SemanticErrorKind.VOID_VALUE_USED,
                                message=f"Variável '{stmt.name}' não pode ser declarada com tipo 'void'.",
                                span=stmt.initializer.span,
                            )
                        )
                    elif initializer_type != stmt.type:
                        self.diagnostics.append(
                            SemanticDiagnostic(
                                kind=SemanticErrorKind.INITIALIZER_TYPE_MISMATCH,
                                message=f"Tipo do inicializador '{initializer_type.value}' não corresponde ao tipo declarado '{stmt.type.value}'.",
                                span=stmt.initializer.span,
                            )
                        )
            return
        
        if isinstance(stmt, CallStmt):
            self.visit_expr(stmt.call)
            return

        if isinstance(stmt, PrintStmt):
            for item in stmt.items:
                if isinstance(item, Expr):
                    self.visit_expr(item)
            return

        if isinstance(stmt, Block):
            self.visit_block(stmt)
            return
        
        if isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                return_type = self.visit_expr(stmt.value)
                if return_type is not None and return_type != self.current_function.return_type:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.RETURN_MISMATCH,
                            message=f"Tipo de retorno '{return_type.value}' não corresponde ao tipo de retorno da função '{self.current_function.return_type.value}'.",
                            span=stmt.value.span,
                        )
                    )
            return
        
        if isinstance(stmt, IfStmt):
            condition_type = self.visit_expr(stmt.condition)
            if condition_type is not None and condition_type != TypeName.BOOL:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                        message=f"Condição do 'if' deve ser do tipo 'bool', mas recebeu '{condition_type.value}'.",
                        span=stmt.condition.span,
                    )
                )
            self.visit_block(stmt.then_block)
            if stmt.else_block is not None:
                self.visit_block(stmt.else_block)
            return
        
        if isinstance(stmt, WhileStmt):
            condition_type = self.visit_expr(stmt.condition)
            if condition_type is not None and condition_type != TypeName.BOOL:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                        message=f"Condição do 'while' deve ser do tipo 'bool', mas recebeu '{condition_type.value}'.",
                        span=stmt.condition.span,
                    )
                )
            self.visit_block(stmt.body)
            return

        if isinstance(stmt, Assignment):
            target_type = self.visit_expr(stmt.target)
            value_type = self.visit_expr(stmt.value)
            if target_type is not None and value_type is not None and target_type != value_type:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.ASSIGNMENT_TYPE_MISMATCH,
                        message=f"Tipo do valor '{value_type.value}' não corresponde ao tipo do alvo '{target_type.value}'.",
                        span=stmt.value.span,
                    )
                )
            return

    def visit_expr(self, expr):
        if isinstance(expr, IntLiteral):
            if expr.value > 9223372036854775807:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.INTEGER_LITERAL_OUT_OF_RANGE,
                        message=f"Literal inteiro '{expr.value}' está fora do intervalo permitido.",
                        span=expr.span,
                    )
                )
            expr.metadata["type"] = TypeName.INT
            return TypeName.INT

        if isinstance(expr, BoolLiteral):
            expr.metadata["type"] = TypeName.BOOL
            return TypeName.BOOL
        
        if isinstance(expr, IdentifierExpr):
            symbol = expr.metadata.get("symbol")
            if symbol is None:
                return None

            expr.metadata["type"] = symbol.type
            return symbol.type

        if isinstance(expr, CallExpr):
            symbol = expr.metadata.get("symbol")
            if symbol is None:
                return None

            arg_types = []
            for argument in expr.arguments:
                arg_types.append(self.visit_expr(argument))

            expected_types = symbol.parameter_types
            if len(arg_types) != len(expected_types):
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.ARITY_MISMATCH,
                        message=f"Função '{expr.name}' espera {len(expected_types)} argumentos, mas recebeu {len(arg_types)}.",
                        span=expr.span,
                    )
                )
            for i in range(min(len(arg_types), len(expected_types))):
                expected_type = expected_types[i]
                actual_type = arg_types[i]

                if actual_type is not None and expected_type != actual_type:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                            message=f"Argumento {i + 1} da função '{expr.name}' espera tipo '{expected_type.value}', mas recebeu tipo '{actual_type.value}'.",
                            span=expr.arguments[i].span,
                        )
                    )

            expr.metadata["type"] = symbol.type
            return symbol.type
        
        if isinstance(expr, BinaryExpr):
            left_type = self.visit_expr(expr.left)
            right_type = self.visit_expr(expr.right)

            if expr.operator in [BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE, BinaryOperator.REMAINDER]:
                if left_type != TypeName.INT or right_type != TypeName.INT:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            message=f"Operador '{expr.operator.value}' requer operandos do tipo 'int', mas recebeu '{left_type.value}' e '{right_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.INT
                return TypeName.INT
            
            elif expr.operator in [BinaryOperator.LESS, BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER, BinaryOperator.GREATER_EQUAL]:
                if left_type != TypeName.INT or right_type != TypeName.INT:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            message=f"Operador '{expr.operator.value}' requer operandos do tipo 'int', mas recebeu '{left_type.value}' e '{right_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL
            
            elif expr.operator in [BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL]:
                if left_type != right_type:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            message=f"Operador '{expr.operator.value}' requer operandos do mesmo tipo, mas recebeu '{left_type.value}' e '{right_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL
            
            elif expr.operator in [BinaryOperator.LOGICAL_AND, BinaryOperator.LOGICAL_OR]:
                if left_type != TypeName.BOOL or right_type != TypeName.BOOL:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            message=f"Operador '{expr.operator.value}' requer operandos do tipo 'bool', mas recebeu '{left_type.value}' e '{right_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL
            
        if isinstance(expr, UnaryExpr):
            operand_type = self.visit_expr(expr.operand)

            if expr.operator == UnaryOperator.NEGATE:
                if operand_type != TypeName.INT:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_UNARY_OPERAND,
                            message=f"Operador '{expr.operator.value}' requer operando do tipo 'int', mas recebeu '{operand_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.INT
                return TypeName.INT
            
            elif expr.operator == UnaryOperator.NOT:
                if operand_type != TypeName.BOOL:
                    self.diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_UNARY_OPERAND,
                            message=f"Operador '{expr.operator.value}' requer operando do tipo 'bool', mas recebeu '{operand_type.value}'.",
                            span=expr.span,
                        )
                    )
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""
    checker = TypeChecker()
    checker.check(program)
    if checker.diagnostics:
        raise SemanticError(checker.diagnostics)