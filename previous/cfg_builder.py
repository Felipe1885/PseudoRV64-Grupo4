"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import Block, FunctionDecl, IfStmt, Stmt, WhileStmt, ReturnStmt, VarDecl, Assignment, CallStmt, PrintStmt, BoolLiteral
from cfg import BlockId, CFG, Branch, Jump, Return, ScopeExit


class CFGBuilder:
    def build(self, function: FunctionDecl) -> CFG:
        self.cfg = CFG(function)
        body_entry = self.cfg.new_block()
        self.cfg.terminate(self.cfg.entry, Jump(body_entry.id))
        continuation = self._build_block(function.body, body_entry.id)
        if continuation is not None:
            self.cfg.terminate(continuation, Jump(self.cfg.fallthrough_exit))
        return self.cfg

    def _build_block(self, block: Block, current: BlockId) -> BlockId | None:
        """Percorra um bloco da AST e devolva sua continuação normal.

        `current` identifica um bloco básico aberto. Comandos sequenciais
        permanecem nele. Comandos de controle podem mudar a continuação.
        None indica que os caminhos deste bloco não alcançam o próximo comando.
        """

        # Analisa os comandos do bloco, caso o fluxo feche (ex: return), current vira None
        for statement in block.statements:
            if current is None:
                break
            current = self._build_statement(statement, current)

        # Caso o fluxo do bloco foi encerrado sem retornar, realiza a saída do escopo, e retorna o ID do bloco atual da CFG.
        if current is not None:
            scope = block.metadata.get("scope")
            if scope is not None:
                self.cfg.blocks[current].operations.append(ScopeExit(scope))

        return current

        #raise NotImplementedError("implemente CFGBuilder._build_block")

    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """Incorpore um comando ao CFG e devolva sua continuação normal."""
        if isinstance(statement, Block):
            return self._build_block(statement, current)

        if isinstance(statement, IfStmt):
            return self._build_if(statement, current)

        if isinstance(statement, WhileStmt):
            return self._build_while(statement, current)

        if isinstance(statement, ReturnStmt):
            self.cfg.terminate(current, Return(statement))
            return None

        if isinstance(statement, (VarDecl, Assignment, CallStmt, PrintStmt)):
            self.cfg.blocks[current].operations.append(statement)
            return current

        raise TypeError(f"comando inesperado: {type(statement).__name__}")
    
        #raise NotImplementedError("implemente CFGBuilder._build_statement")

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        """Construa o fluxo da condicional e devolva sua continuação."""
        then_block = self.cfg.new_block()

        # Para um if sem else, verdadeiro entra no then_block, falso vai para o merge_block
        if statement.else_block is None:
            merge_block = self.cfg.new_block()
            self.cfg.terminate(current, Branch(statement.condition, then_block.id, merge_block.id))
            then_continuation = self._build_block(statement.then_block, then_block.id)
            if then_continuation is not None:
                self.cfg.terminate(then_continuation, Jump(merge_block.id))
            return merge_block.id

        # Para um if com else, verdadeiro entra no then_block, falso vai para o else_block
        else_block = self.cfg.new_block()
        self.cfg.terminate(current, Branch(statement.condition, then_block.id, else_block.id))
        then_continuation = self._build_block(statement.then_block, then_block.id)
        else_continuation = self._build_block(statement.else_block, else_block.id)

        # Para caso todos os caminhos tiverem return, retorna None
        if then_continuation is None and else_continuation is None:
            return None

        # Caso um caminho não tenha return, vai para o merge_block
        merge_block = self.cfg.new_block()
        if then_continuation is not None:
            self.cfg.terminate(then_continuation, Jump(merge_block.id))
        if else_continuation is not None:
            self.cfg.terminate(else_continuation, Jump(merge_block.id))
        return merge_block.id

        #raise NotImplementedError("implemente CFGBuilder._build_if")

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        """Construa o fluxo do laço e devolva sua continuação."""
        condition_block = self.cfg.new_block()
        body_block = self.cfg.new_block()
        self.cfg.terminate(current, Jump(condition_block.id))

        # Caso o while seja infinito, não tem continuação normal, então retorna None
        if isinstance(statement.condition, BoolLiteral) and statement.condition.value is True:
            self.cfg.terminate(condition_block.id, Jump(body_block.id))
            body_continuation = self._build_block(statement.body, body_block.id)
            if body_continuation is not None:
                self.cfg.terminate(body_continuation, Jump(condition_block.id))
            return None

        # Caso o while tenha condição, verdadeiro vai para o body_block, falso vai para o after_block
        after_block = self.cfg.new_block()
        self.cfg.terminate(condition_block.id, Branch(statement.condition, body_block.id, after_block.id))
        body_continuation = self._build_block(statement.body, body_block.id)
        if body_continuation is not None:
            self.cfg.terminate(body_continuation, Jump(condition_block.id))

        return after_block.id

        #raise NotImplementedError("implemente CFGBuilder._build_while")
