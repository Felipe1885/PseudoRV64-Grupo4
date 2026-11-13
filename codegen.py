"""Pontos de implementação da geração de comandos e expressões."""

import load_previous
from ir import (
    Context,
    ProgramIR,
    FunctionIR,
    Add,
    Addi,
    Bge,
    Beq,
    Bne,
    Bnez,
    Blt,
    Call,
    Div,
    Jump,
    LabelInstr,
    Li,
    Move,
    Mul,
    Neg,
    Param,
    PrintBool,
    PrintInt,
    PrintString,
    Rem,
    Return,
    Slli,
    Slt,
    Seqz,
    Snez,
    Sub,
    Xor,
)

from ast_nodes import (
    Assignment,
    BinaryOperator,
    Block,
    CallStmt,
    IfStmt,
    IntLiteral,
    PrintStmt,
    ReturnStmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    UnaryOperator,
    VarDecl,
    WhileStmt,
)

from catalogue import catalogue
from patterns import COND, EFFECT, IMM12, POW2, REG
from selector import Selector


class CodeGenerator:
    """Traduza comandos diretamente e expressões por seleção de padrões."""

    def __init__(self):
        self.selector = Selector(catalogue())
        self.program = None
        self.context = None

    def generate(self, program):
        """Traduza funções e comandos. Selecione expressões com DP."""
        # Inicializa o programa de saída
        self.program = ProgramIR()

        # Para cada declaração de função
        for declaration in program.functions:
            # Inicializa o contexto de tradução da função
            function = declaration.metadata["symbol"]
            function_ir = FunctionIR(function)
            self.context = Context(function_ir, self.program)

            # Inicializa os parâmetros da função
            for index, parameter in enumerate(declaration.parameters):
                symbol = parameter.metadata["symbol"]
                register = self.context.variable(symbol)
                function_ir.instructions.append(Param(register, index, origin=parameter.span))

            # Traduz o corpo da função
            self.statement(declaration.body)

            # Garante que funções void terminem com return
            if (function.type is TypeName.VOID and (not function_ir.instructions or not isinstance(function_ir.instructions[-1], Return))):
                function_ir.instructions.append(Return(None, origin=declaration.span))

            # Adiciona a função traduzida ao programa de saída
            self.program.functions.append(function_ir)

        return self.program

    def expression(self, node, result_class, true_label=None, false_label=None):
        """Selecione e reconstrua uma expressão, preservando curto-circuito."""
        
        # Se a expressão for um literal inteiro ou uma potência de dois, retorne o valor literal
        if result_class in [IMM12, POW2]:
            return self._literal_value(node)

        # Se a expressão for uma chamada de função com efeito (resultado descartado), avalie os argumentos e emita a chamada
        if result_class is EFFECT:
            arguments = tuple(
                self.expression(argument, REG)
                for argument in node.arguments
            )

            self.context.emit(
                Call(
                    None,
                    node.metadata["symbol"],
                    arguments,
                    origin=node.span,
                )
            )
            return None

        # As outras expressões (REG e COND) podem produzir registradores ou alterar o fluxo de controle,
        # por isso utilizamos a tabela de seleção
        table = self.selector.analyze(node)
        choice = table.lookup(node, result_class)

        # Se a expressão for condicional, emita o código de salto apropriado para os rótulos verdadeiro e falso
        if result_class is COND:
            self._emit_condition(
                node,
                choice.rule.action,
                true_label,
                false_label,
            )
            return None

        # Se a expressão for um registrador, avalie os filhos e emita a ação correspondente
        if result_class is REG:
            # Operações lógicas precisam materializar o resultado 0 ou 1
            if choice.rule.action == "emitir_logico_reg":
                result = self.context.temp()
                true_target = self.context.label()
                false_target = self.context.label()
                end_target = self.context.label()

                self.expression(
                    node,
                    COND,
                    true_label=true_target,
                    false_label=false_target,
                )

                self.context.emit(LabelInstr(true_target, origin=node.span))
                self.context.emit(Li(result, 1, origin=node.span))
                self.context.emit(Jump(end_target, origin=node.span))

                self.context.emit(LabelInstr(false_target, origin=node.span))
                self.context.emit(Li(result, 0, origin=node.span))

                self.context.emit(LabelInstr(end_target, origin=node.span))
                return result

            # Para todas as outras expressões, avalie os filhos e emita a ação correspondente
            values = [
                self.expression(child, child_class)
                for child, child_class in choice.subproblems
            ]

            # Emite a ação correspondente
            return self._emit_action(node, choice.rule.action, values)

    def statement(self, node):
        """Traduza um comando ad hoc."""
        # Se for um bloco, traduza cada comando dentro dele.
        if isinstance(node, Block):
            for statement in node.statements:
                self.statement(statement)
            return

        # Se for uma declaração de variável, mova o valor inicial para o registrador da variável, se houver inicialização
        if isinstance(node, VarDecl):
            if node.initializer is not None:
                target = self.context.variable(node.metadata["symbol"])
                value = self.expression(node.initializer, REG)
                self.context.emit(Move(target, value, origin=node.span))

            return
    
        # Se for uma atribuição, mova o valor para o registrador da variável
        if isinstance(node, Assignment):
            target = self.context.variable(node.target.metadata["symbol"])
            value = self.expression(node.value, REG)
            self.context.emit(Move(target, value, origin=node.span))
            return

        # Se for uma chamada de função, avalie os argumentos e emita a chamada
        if isinstance(node, CallStmt):
            arguments = tuple(
                self.expression(argument, REG)
                for argument in node.call.arguments
            )

            self.context.emit(
                Call(
                    None,
                    node.call.metadata["symbol"],
                    arguments,
                    origin=node.call.span,
                )
            )
            return

        # Se for um comando de impressão, imprima cada item
        if isinstance(node, PrintStmt):
            for item in node.items:
                # Se o item for uma string literal, obtenha a string do pool e emita a instrução de impressão de string
                if isinstance(item, StringLiteral):
                    string = self.context.string(item.value)
                    self.context.emit(PrintString(string, origin=item.span))
                    continue

                # Se o item for uma expressão, avalie a expressão e emita a instrução de impressão apropriada para o tipo do item
                value = self.expression(item, REG)
                if item.metadata.get("type") is TypeName.BOOL:
                    self.context.emit(PrintBool(value, origin=item.span))
                else:
                    self.context.emit(PrintInt(value, origin=item.span))

            # Cada print termina com uma quebra de linha compartilhada no pool.
            newline = self.context.string("\n")
            self.context.emit(PrintString(newline, origin=node.span))
            return

        # Se for um comando if, avalie a condição e emita os blocos then e else apropriados
        if isinstance(node, IfStmt):
            then_label = self.context.label()
            end_label = self.context.label()

            # Se não houver bloco else, apenas avalie a condição e emita o bloco then seguido pelo rótulo de fim
            if node.else_block is None:
                self.expression(
                    node.condition,
                    COND,
                    true_label=then_label,
                    false_label=end_label,
                )

                self.context.emit(LabelInstr(then_label, origin=node.span))
                self.statement(node.then_block)
                self.context.emit(LabelInstr(end_label, origin=node.span))
                return

            # Se houver um bloco else, avalie a condição e emita os blocos then e else apropriados, seguidos pelo rótulo de fim
            else_label = self.context.label()

            self.expression(
                node.condition,
                COND,
                true_label=then_label,
                false_label=else_label,
            )

            self.context.emit(LabelInstr(then_label, origin=node.span))
            self.statement(node.then_block)
            self.context.emit(Jump(end_label, origin=node.span))
            
            self.context.emit(LabelInstr(else_label, origin=node.span))
            self.statement(node.else_block)

            self.context.emit(LabelInstr(end_label, origin=node.span))
            return

        # Se for um comando while, avalie a condição e emita o bloco do corpo apropriado, seguido pelo rótulo de fim
        if isinstance(node, WhileStmt):
            condition_label = self.context.label()
            body_label = self.context.label()
            end_label = self.context.label()

            self.context.emit(LabelInstr(condition_label, origin=node.span))

            self.expression(
                node.condition,
                COND,
                true_label=body_label,
                false_label=end_label,
            )

            self.context.emit(LabelInstr(body_label, origin=node.span))
            self.statement(node.body)
            self.context.emit(Jump(condition_label, origin=node.span))
            self.context.emit(LabelInstr(end_label, origin=node.span))
            return

        # Se for um comando de retorno, avalie o valor de retorno (se houver) e emita a instrução de retorno apropriada
        if isinstance(node, ReturnStmt):
            value = self.expression(node.value, REG) if node.value is not None else None
            self.context.emit(Return(value, origin=node.span))
            return

    # Função auxiliar para emitir ações correspondentes a padrões de expressão selecionados
    def _emit_action(self, node, action, values):
        if action == "emitir_li_inteiro":
            result = self.context.temp()
            self.context.emit(Li(result, self._literal_value(node), origin=node.span))
            return result

        if action == "emitir_li_bool":
            result = self.context.temp()
            self.context.emit(Li(result, int(node.value), origin=node.span))
            return result

        if action == "reutilizar_vreg":
            return self.context.variable(node.metadata["symbol"])

        if action == "emitir_neg":
            result = self.context.temp()
            self.context.emit(Neg(result, values[0], origin=node.span))
            return result

        if action == "emitir_aritmetica":
            result = self.context.temp()
            instructions = {
                BinaryOperator.ADD: Add,
                BinaryOperator.SUBTRACT: Sub,
                BinaryOperator.MULTIPLY: Mul,
                BinaryOperator.DIVIDE: Div,
                BinaryOperator.REMAINDER: Rem,
            }

            instruction = instructions[node.operator]
            self.context.emit(instruction(result, values[0], values[1], origin=node.span))
            return result

        if action == "emitir_soma_imediato_direita":
            result = self.context.temp()
            immediate = self._literal_value(node.right)

            self.context.emit(Addi(result, values[0], immediate, origin=node.span))
            return result

        if action == "emitir_soma_imediato_esquerda":
            result = self.context.temp()
            immediate = self._literal_value(node.left)

            self.context.emit(Addi(result, values[1], immediate, origin=node.span))
            return result

        if action == "emitir_subtracao_imediato":
            result = self.context.temp()
            immediate = -self._literal_value(node.right)

            self.context.emit(Addi(result, values[0], immediate, origin=node.span))
            return result

        if action == "emitir_slli_direita":
            result = self.context.temp()
            power = self._literal_value(node.right)
            shift = power.bit_length() - 1 # Calcula o deslocamento a partir do expoente da potência de dois

            self.context.emit(Slli(result, values[0], shift, origin=node.span))
            return result

        if action == "emitir_slli_esquerda":
            result = self.context.temp()
            power = self._literal_value(node.left)
            shift = power.bit_length() - 1 # Calcula o deslocamento a partir do expoente da potência de dois
            
            self.context.emit(Slli(result, values[1], shift, origin=node.span))
            return result

        if action == "emitir_slt":
            result = self.context.temp()

            # A instrução Slt testa apenas "menor que".
            # Para "maior que", troca-se a ordem dos operandos:
            # a > b equivale a b < a
            if node.operator is BinaryOperator.GREATER:
                lhs, rhs = values[1], values[0]
            else:
                lhs, rhs = values[0], values[1]

            self.context.emit(Slt(result, lhs, rhs, origin=node.span))
            return result

        if action == "emitir_slt_seqz":
            comparison = self.context.temp()
            result = self.context.temp()

            # Slt calcula a relação complementar:
            # a <= b equivale a não (b < a)
            # a >= b equivale a não (a < b)
            if node.operator is BinaryOperator.LESS_EQUAL:
                lhs, rhs = values[1], values[0]
            else:
                lhs, rhs = values[0], values[1]

            self.context.emit(Slt(comparison, lhs, rhs, origin=node.span))
            # Seqz inverte o resultado de Slt
            self.context.emit(Seqz(result, comparison, origin=node.span))
            return result

        # Comparação de igualdade e diferença é feita com XOR seguido de SEQZ ou SNEZ
        if action == "emitir_xor_seqz":
            comparison = self.context.temp()
            result = self.context.temp()

            self.context.emit(Xor(comparison, values[0], values[1], origin=node.span))

            if node.operator is BinaryOperator.EQUAL:
                self.context.emit(Seqz(result, comparison, origin=node.span))
            else:
                self.context.emit(Snez(result, comparison, origin=node.span))

            return result

        if action == "emitir_not_reg":
            result = self.context.temp()
            self.context.emit(Seqz(result, values[0], origin=node.span))
            return result

        if action == "emitir_chamada_reg":
            result = self.context.temp()

            self.context.emit(
                Call(
                    result,
                    node.metadata["symbol"],
                    tuple(values),
                    origin=node.span,
                )
            )
            return result

    # Função auxiliar para emitir ações correspondentes a padrões de expressão selecionados, quando o resultado é condicional
    def _emit_condition(self, node, action, true_label, false_label):
        if action == "emitir_bool_literal_cond":
            target = true_label if node.value else false_label
            self.context.emit(Jump(target, origin=node.span))
            return

        if action == "emitir_identificador_cond":
            value = self.context.variable(node.metadata["symbol"])

            self.context.emit(Bnez(value, true_label, origin=node.span))
            self.context.emit(Jump(false_label, origin=node.span))
            return

        if action == "emitir_not_cond":
            self.expression(
                node.operand,
                COND,
                true_label=false_label,
                false_label=true_label,
            )
            return

        # Para operadores lógicos, realizar curto-circuito
        if action == "emitir_logico_cond":
            intermediate = self.context.label()

            # Se o operador for AND, avalie o lado esquerdo e, se verdadeiro, avalie o lado direito.
            # Caso contrário, vá direto para o rótulo falso
            if node.operator is BinaryOperator.LOGICAL_AND:
                self.expression(
                    node.left,
                    COND,
                    true_label=intermediate,
                    false_label=false_label,
                )

                self.context.emit(LabelInstr(intermediate, origin=node.span))

                self.expression(
                    node.right,
                    COND,
                    true_label=true_label,
                    false_label=false_label,
                )
                return

            # Se o operador for OR, avalie o lado esquerdo e, se falso, avalie o lado direito.
            # Caso contrário, vá direto para o rótulo verdadeiro
            self.expression(
                node.left,
                COND,
                true_label=true_label,
                false_label=intermediate,
            )

            self.context.emit(LabelInstr(intermediate, origin=node.span))

            self.expression(
                node.right,
                COND,
                true_label=true_label,
                false_label=false_label,
            )
            return

        if action == "emitir_comparacao_cond":
            lhs = self.expression(node.left, REG)
            rhs = self.expression(node.right, REG)

            if node.operator is BinaryOperator.LESS:
                self.context.emit(Blt(lhs, rhs, true_label, origin=node.span))
            elif node.operator is BinaryOperator.GREATER:
                self.context.emit(Blt(rhs, lhs, true_label, origin=node.span))
            elif node.operator is BinaryOperator.LESS_EQUAL:
                self.context.emit(Bge(rhs, lhs, true_label, origin=node.span))
            elif node.operator is BinaryOperator.GREATER_EQUAL:
                self.context.emit(Bge(lhs, rhs, true_label, origin=node.span))
            elif node.operator is BinaryOperator.EQUAL:
                self.context.emit(Beq(lhs, rhs, true_label, origin=node.span))
            elif node.operator is BinaryOperator.NOT_EQUAL:
                self.context.emit(Bne(lhs, rhs, true_label, origin=node.span))

            self.context.emit(Jump(false_label, origin=node.span))
            return

        if action == "emitir_call_cond":
            arguments = tuple(
                self.expression(argument, REG)
                for argument in node.arguments
            )
            result = self.context.temp()

            self.context.emit(
                Call(
                    result,
                    node.metadata["symbol"],
                    arguments,
                    origin=node.span,
                )
            )
            self.context.emit(Bnez(result, true_label, origin=node.span))
            self.context.emit(Jump(false_label, origin=node.span))
            return

    # Função auxiliar para obter o valor de um literal inteiro, inclusive negativo.
    def _literal_value(self, node):
        if isinstance(node, IntLiteral):
            return node.value

        if (isinstance(node, UnaryExpr) and node.operator is UnaryOperator.NEGATE and isinstance(node.operand, IntLiteral)):
            return -node.operand.value