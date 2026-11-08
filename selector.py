"""Ponto de implementação do reconhecimento de padrões e custos mínimos."""

from patterns import *


class Selector:
    """Selecione coberturas sem executar expressões ou emitir instruções."""

    def __init__(self, rules):
        self.rules = tuple(rules)

    def analyze(self, expr):
        """Calcule mínimos por nó/classe sem emitir instruções."""
        table = SelectionTable()
        self._visit(expr, table)
        return table
        #raise NotImplementedError("implemente matching e DP")

    def _visit(self, node, table: SelectionTable):
        # Calcula a tabela para os filhos do nó
        for child in children(node):
            self._visit(child, table)

        # Testa as regras para o nó atual
        for rule in self.rules:
            subproblems = self._match_pattern(node, rule.pattern)
            if subproblems is None:
                continue

            # Verifica se todos os filhos têm cobertura
            total_cost = rule.cost
            possible = True
            for sub_node, sub_class in subproblems:
                choice = table.lookup(sub_node, sub_class)
                if choice is None:
                    possible = False
                    break
                total_cost += choice.cost

            if not possible:
                continue

            # Guarda a a escolha de menor custo para (node, rule.result)
            current_best = table.lookup(node, rule.result)
            if current_best is None or total_cost < current_best.cost:
                table.put(
                    node,
                    rule.result,
                    Choice(cost=total_cost, rule=rule, subproblems=tuple(subproblems)),
                )

    def _match_pattern(self, node, pattern: Pattern):
        """Verifica se o nó corresponde em 'pattern' e retorna a lista de subproblemas"""
        # Checa o tipo da classe da AST (ex: BinaryExpr)
        if pattern.kind is not None and not isinstance(node, pattern.kind):
            return None

        # Checa o operador (ex: BinnaryOperator.ADD)
        if pattern.operator is not None:
            if getattr(node, "operator", None) != pattern.operator:
                return None

        # Checa o predicado (ex: imm12)
        if pattern.predicate is not None and not pattern.predicate(node):
            return None

        # Padrão com predicado e sem filhos (ex: UnaryExpr em _is_signed_literal)
        if not pattern.children and pattern.predicate is not None:
            return []

        # Caso de chamadas CallExpr, com filho Args
        if len(pattern.children) == 1 and isinstance(pattern.children[0], Args):
            needed_class = pattern.children[0].result
            return [(arg, needed_class) for arg in children(node)]

        # Nos demais casos, a quantidade de filhos da AST deve ser a mesma
        if len(children(node)) != len(pattern.children):
            return None

        # Percorre cada filho do nó junto com o padrão correspondente, construindo a lista de subproblemas
        subproblems = []
        for child_node, child_spec in zip(children(node), pattern.children):
            # Se o padrão exige uma classe (Need), registra o subproblema (filho, classe)
            if isinstance(child_spec, Need):
                subproblems.append((child_node, child_spec.result))
            # Se o padrão possui outro sub-padrão aninhado, valida recursivamente
            elif isinstance(child_spec, Pattern):
                nested = self._match_pattern(child_node, child_spec)
                if nested is None:
                    return None
                subproblems.extend(nested)
            else:
                return None

        return subproblems