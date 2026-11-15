"""Alcance no CFG. O percurso da AST já foi realizado pelo builder."""

from __future__ import annotations

from cfg import BlockId, CFG


def compute_reachable(cfg: CFG) -> set[BlockId]:
    """Devolva os IDs alcançáveis a partir da entrada, incluindo a entrada."""

    reachable: set[BlockId] = set()
    pending = [cfg.entry]
    while pending:
        current = pending.pop()
        if current in reachable:
            continue

        # TODO: registre a visita e coloque os sucessores na lista de trabalho.
        # O conjunto de visitados precisa impedir repetição infinita nos ciclos.
        reachable.add(current)
        pending.extend(cfg.blocks[current].successors)
        
        #raise NotImplementedError("implemente compute_reachable")
    return reachable
