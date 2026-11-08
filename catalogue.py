"""Ponto de implementação das regras declarativas do enunciado."""

import load_previous
from ast_nodes import (
    BinaryExpr,
    BinaryOperator,
    BoolLiteral,
    CallExpr,
    IdentifierExpr,
    TypeName,
    UnaryExpr,
    UnaryOperator,
)
from patterns import (
    Args, COND, EFFECT, IMM12, POW2, REG,
    Need, Pattern, Rule,
    imm12, neg_imm12, pow2, signed_literal,
)


def _is_signed_literal(node):
    return signed_literal(node) is not None

def _type_of(node):
    """Tipo anotado pelo frontend; se faltar, o tipo do símbolo."""
    t = node.metadata.get("type")
    if t is None:
        t = getattr(node.metadata.get("symbol"), "type", None)
    return t


def _is_bool(node):
    return _type_of(node) == TypeName.BOOL

def _is_non_void(node):
    return _type_of(node) in (TypeName.INT, TypeName.BOOL)

def catalogue():
    """Codifique o catálogo do enunciado com Rule e Pattern."""
    #raise NotImplementedError("implemente o catálogo")
    rules = []

    # Folhas
    rules.append(Rule("literal_inteiro_reg", REG,
                      Pattern(predicate=_is_signed_literal),
                      1, "emitir_li_inteiro"))
    rules.append(Rule("literal_bool_reg", REG,
                      Pattern(BoolLiteral),
                      1, "emitir_li_bool"))
    rules.append(Rule("identificador_reg", REG,
                      Pattern(IdentifierExpr),
                      0, "reutilizar_vreg"))
    rules.append(Rule("literal_imm12", IMM12,
                      Pattern(predicate=imm12),
                      0, "literal_imediato"))
    rules.append(Rule("literal_pow2", POW2,
                      Pattern(predicate=pow2),
                      0, "literal_expoente"))

    # Aritmética
    def binary(op, left, right):
        return Pattern(BinaryExpr, op, (left, right))

    rules.append(Rule("negacao_aritmetica", REG,
                      Pattern(UnaryExpr, UnaryOperator.NEGATE, (Need(REG),)),
                      1, "emitir_neg"))

    for name, op in (("soma", BinaryOperator.ADD),
                     ("subtracao", BinaryOperator.SUBTRACT),
                     ("multiplicacao", BinaryOperator.MULTIPLY),
                     ("divisao", BinaryOperator.DIVIDE),
                     ("resto", BinaryOperator.REMAINDER)):
        rules.append(Rule(f"{name}_geral", REG,
                          binary(op, Need(REG), Need(REG)),
                          1, "emitir_aritmetica"))

    rules.append(Rule("soma_imediato_direita", REG,
                      binary(BinaryOperator.ADD, Need(REG), Need(IMM12)),
                      1, "emitir_soma_imediato_direita"))
    rules.append(Rule("soma_imediato_esquerda", REG,
                      binary(BinaryOperator.ADD, Need(IMM12), Need(REG)),
                      1, "emitir_soma_imediato_esquerda"))

    rules.append(Rule("subtracao_imediato", REG,
                      binary(BinaryOperator.SUBTRACT, Need(REG),
                             Pattern(predicate=neg_imm12)),
                      1, "emitir_subtracao_imediato"))

    rules.append(Rule("multiplicacao_slli_direita", REG,
                      binary(BinaryOperator.MULTIPLY, Need(REG), Need(POW2)),
                      1, "emitir_slli_direita"))
    rules.append(Rule("multiplicacao_slli_esquerda", REG,
                      binary(BinaryOperator.MULTIPLY, Need(POW2), Need(REG)),
                      1, "emitir_slli_esquerda"))

    # Comparações como valor (REG)
    for name, op in (("menor", BinaryOperator.LESS),
                     ("maior", BinaryOperator.GREATER)):
        rules.append(Rule(f"{name}_reg", REG,
                          binary(op, Need(REG), Need(REG)),
                          1, "emitir_slt"))
    for name, op in (("menor_igual", BinaryOperator.LESS_EQUAL),
                     ("maior_igual", BinaryOperator.GREATER_EQUAL)):
        rules.append(Rule(f"{name}_reg", REG,
                          binary(op, Need(REG), Need(REG)),
                          2, "emitir_slt_seqz"))
    for name, op in (("igual", BinaryOperator.EQUAL),
                     ("diferente", BinaryOperator.NOT_EQUAL)):
        rules.append(Rule(f"{name}_reg", REG,
                          binary(op, Need(REG), Need(REG)),
                          2, "emitir_xor_seqz"))

    # Comparações como condição (COND)
    for name, op in (("menor", BinaryOperator.LESS),
                     ("menor_igual", BinaryOperator.LESS_EQUAL),
                     ("maior", BinaryOperator.GREATER),
                     ("maior_igual", BinaryOperator.GREATER_EQUAL),
                     ("igual", BinaryOperator.EQUAL),
                     ("diferente", BinaryOperator.NOT_EQUAL)):
        rules.append(Rule(f"{name}_cond", COND,
                          binary(op, Need(REG), Need(REG)),
                          2, "emitir_comparacao_cond"))

    # Lógica
    rules.append(Rule("negacao_logica_reg", REG,
                      Pattern(UnaryExpr, UnaryOperator.NOT, (Need(REG),)),
                      1, "emitir_not_reg"))
    rules.append(Rule("negacao_logica_cond", COND,
                      Pattern(UnaryExpr, UnaryOperator.NOT, (Need(COND),)),
                      0, "emitir_not_cond"))
    for name, op in (("e", BinaryOperator.LOGICAL_AND),
                     ("ou", BinaryOperator.LOGICAL_OR)):
        rules.append(Rule(f"{name}_cond", COND,
                          binary(op, Need(COND), Need(COND)),
                          0, "emitir_logico_cond"))
        rules.append(Rule(f"{name}_reg", REG,
                          binary(op, Need(COND), Need(COND)),
                          3, "emitir_logico_reg"))

    rules.append(Rule("literal_bool_cond", COND,
                      Pattern(BoolLiteral),
                      1, "emitir_bool_literal_cond"))
    rules.append(Rule("identificador_bool_cond", COND,
                      Pattern(IdentifierExpr, predicate=_is_bool),
                      2, "emitir_identificador_cond"))

    # Chamadas de função
    rules.append(Rule("chamada_reg", REG,
                      Pattern(CallExpr, children=(Args(REG),), predicate=_is_non_void),
                      1, "emitir_chamada_reg"))
    rules.append(Rule("chamada_void", EFFECT,
                      Pattern(CallExpr, children=(Args(REG),)),
                      1, "emitir_call_effect"))
    rules.append(Rule("chamada_bool_cond", COND,
                      Pattern(CallExpr, children=(Args(REG),), predicate=_is_bool),
                      3, "emitir_call_cond"))

    return rules
