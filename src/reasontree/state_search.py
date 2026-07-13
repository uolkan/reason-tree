from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


StateT = TypeVar("StateT")
ActionT = TypeVar("ActionT")
MATE_SCORE = 100_000


class StateActionAdapter(Protocol[StateT, ActionT]):
    """Domain contract for a bounded adversarial state-action search."""

    def actions(self, state: StateT, *, tactical_only: bool) -> list[ActionT]: ...

    def transition(self, state: StateT, action: ActionT) -> StateT: ...

    def terminal_score(self, state: StateT, ply: int) -> int | None: ...

    def heuristic_score(self, state: StateT) -> int: ...

    def action_id(self, action: ActionT) -> str: ...


@dataclass(frozen=True)
class BoundedSearchConfig:
    depth: int = 3
    quiescence_depth: int = 0
    top_k: int = 3
    max_nodes: int = 100_000
    timeout_s: float = 10.0


@dataclass(frozen=True)
class BoundedBranch:
    action: str
    score: int
    principal_variation: list[str]


@dataclass(frozen=True)
class BoundedSearchResult:
    branches: list[BoundedBranch]
    nodes: int
    completed: bool
    wall_seconds: float


class SearchLimitReached(RuntimeError):
    pass


class BoundedStateSearch(Generic[StateT, ActionT]):
    """Provider-neutral negamax controller over an executable domain adapter.

    Scores are always from the perspective of the actor at the current state.
    The adapter is responsible for making transitions real and for marking a
    heuristic as such when it is not an authoritative verifier.
    """

    def __init__(
        self,
        adapter: StateActionAdapter[StateT, ActionT],
        config: BoundedSearchConfig | None = None,
    ):
        self.adapter = adapter
        self.config = config or BoundedSearchConfig()
        self.nodes = 0
        self.deadline = 0.0

    def search(self, initial_state: StateT) -> BoundedSearchResult:
        started = time.monotonic()
        self.nodes = 0
        self.deadline = started + self.config.timeout_s
        completed = True
        scored: list[tuple[int, str, list[str]]] = []
        try:
            for action in self.adapter.actions(initial_state, tactical_only=False):
                self._tick()
                child = self.adapter.transition(initial_state, action)
                child_score, child_pv = self._negamax(
                    child,
                    self.config.depth - 1,
                    -MATE_SCORE,
                    MATE_SCORE,
                    ply=1,
                )
                action_id = self.adapter.action_id(action)
                scored.append((-child_score, action_id, [action_id, *child_pv]))
        except SearchLimitReached:
            completed = False

        scored.sort(key=lambda item: (-item[0], item[1]))
        return BoundedSearchResult(
            branches=[
                BoundedBranch(action=action_id, score=score, principal_variation=pv)
                for score, action_id, pv in scored[: self.config.top_k]
            ],
            nodes=self.nodes,
            completed=completed,
            wall_seconds=round(time.monotonic() - started, 4),
        )

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes > self.config.max_nodes or time.monotonic() > self.deadline:
            raise SearchLimitReached

    def _negamax(
        self,
        state: StateT,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> tuple[int, list[str]]:
        self._tick()
        terminal = self.adapter.terminal_score(state, ply)
        if terminal is not None:
            return terminal, []
        if depth <= 0:
            return self._quiescence(state, alpha, beta, self.config.quiescence_depth, ply), []

        best_line: list[str] = []
        for action in self.adapter.actions(state, tactical_only=False):
            child = self.adapter.transition(state, action)
            child_score, child_pv = self._negamax(child, depth - 1, -beta, -alpha, ply + 1)
            score = -child_score
            if score > alpha:
                alpha = score
                best_line = [self.adapter.action_id(action), *child_pv]
            if alpha >= beta:
                break
        return alpha, best_line

    def _quiescence(
        self,
        state: StateT,
        alpha: int,
        beta: int,
        depth: int,
        ply: int,
    ) -> int:
        self._tick()
        terminal = self.adapter.terminal_score(state, ply)
        if terminal is not None:
            return terminal
        stand_pat = self.adapter.heuristic_score(state)
        if depth <= 0:
            return stand_pat
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        for action in self.adapter.actions(state, tactical_only=True):
            child = self.adapter.transition(state, action)
            score = -self._quiescence(child, -beta, -alpha, depth - 1, ply + 1)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha
