from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

import chess

from .state_search import StateActionAdapter


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
MATE_SCORE = 100_000


@dataclass(frozen=True)
class SearchConfig:
    depth: int = 3
    quiescence_depth: int = 3
    top_k: int = 3
    max_nodes: int = 250_000
    timeout_s: float = 10.0


@dataclass(frozen=True)
class SearchBranch:
    move_uci: str
    move_san: str
    score_cp: int
    principal_variation_uci: list[str]
    principal_variation_san: list[str]


@dataclass(frozen=True)
class SearchResult:
    branches: list[SearchBranch]
    nodes: int
    completed: bool
    wall_seconds: float
    config: SearchConfig


class SearchLimitReached(RuntimeError):
    pass


class ChessStateAdapter(StateActionAdapter[chess.Board, chess.Move]):
    """Copy-based chess implementation of the reusable state-action contract."""

    def actions(self, state: chess.Board, *, tactical_only: bool) -> list[chess.Move]:
        moves = list(state.legal_moves)
        if tactical_only:
            moves = [
                move
                for move in moves
                if state.is_capture(move) or move.promotion is not None or state.gives_check(move)
            ]
        return sorted(moves, key=lambda move: ChessTreeSearch._move_priority(state, move), reverse=True)

    def transition(self, state: chess.Board, action: chess.Move) -> chess.Board:
        child = state.copy(stack=False)
        child.push(action)
        return child

    def terminal_score(self, state: chess.Board, ply: int) -> int | None:
        return ChessTreeSearch._terminal_score(state, ply)

    def heuristic_score(self, state: chess.Board) -> int:
        return ChessTreeSearch._static_score(state)

    def action_id(self, action: chess.Move) -> str:
        return action.uci()


class ChessTreeSearch:
    """Small deterministic state-action tree for tactical verification.

    This is deliberately not a full chess engine. It makes the ReasonTree
    control loop concrete: enumerate legal actions, transition real board
    states, let the opponent choose the worst reply, and score terminal or
    material outcomes under a strict node/time budget.
    """

    def __init__(self, config: SearchConfig | None = None):
        self.config = config or SearchConfig()
        self.nodes = 0
        self.deadline = 0.0

    def search(self, board: chess.Board) -> SearchResult:
        started = time.monotonic()
        self.nodes = 0
        self.deadline = started + self.config.timeout_s
        completed = True
        scored: list[tuple[int, chess.Move, list[chess.Move]]] = []

        try:
            for move in self._ordered_moves(board, tactical_only=False):
                self._tick()
                board.push(move)
                try:
                    score, pv = self._negamax(
                        board,
                        self.config.depth - 1,
                        -MATE_SCORE,
                        MATE_SCORE,
                        ply=1,
                    )
                finally:
                    board.pop()
                scored.append((-score, move, pv))
        except SearchLimitReached:
            completed = False

        scored.sort(key=lambda item: (-item[0], item[1].uci()))
        branches = [self._render_branch(board, score, move, pv) for score, move, pv in scored[: self.config.top_k]]
        return SearchResult(
            branches=branches,
            nodes=self.nodes,
            completed=completed,
            wall_seconds=round(time.monotonic() - started, 4),
            config=self.config,
        )

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes > self.config.max_nodes or time.monotonic() > self.deadline:
            raise SearchLimitReached

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> tuple[int, list[chess.Move]]:
        self._tick()
        terminal = self._terminal_score(board, ply)
        if terminal is not None:
            return terminal, []
        if depth <= 0:
            return self._quiescence(board, alpha, beta, self.config.quiescence_depth, ply), []

        best_line: list[chess.Move] = []
        for move in self._ordered_moves(board, tactical_only=False):
            board.push(move)
            try:
                child_score, child_pv = self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop()
            score = -child_score
            if score > alpha:
                alpha = score
                best_line = [move, *child_pv]
            if alpha >= beta:
                break
        return alpha, best_line

    def _quiescence(
        self,
        board: chess.Board,
        alpha: int,
        beta: int,
        depth: int,
        ply: int,
    ) -> int:
        self._tick()
        terminal = self._terminal_score(board, ply)
        if terminal is not None:
            return terminal

        stand_pat = self._static_score(board)
        if depth <= 0:
            return stand_pat
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        for move in self._ordered_moves(board, tactical_only=True):
            board.push(move)
            try:
                score = -self._quiescence(board, -beta, -alpha, depth - 1, ply + 1)
            finally:
                board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    @staticmethod
    def _terminal_score(board: chess.Board, ply: int) -> int | None:
        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
            return 0
        return None

    @staticmethod
    def _static_score(board: chess.Board) -> int:
        white_score = 0
        for square, piece in board.piece_map().items():
            value = PIECE_VALUES[piece.piece_type]
            if piece.piece_type == chess.PAWN:
                rank = chess.square_rank(square)
                value += (rank if piece.color == chess.WHITE else 7 - rank) * 8
            white_score += value if piece.color == chess.WHITE else -value
        return white_score if board.turn == chess.WHITE else -white_score

    @staticmethod
    def _move_priority(board: chess.Board, move: chess.Move) -> tuple[int, str]:
        priority = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            victim_value = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            priority += 10_000 + victim_value - attacker_value // 10
        if move.promotion:
            priority += 9_000 + PIECE_VALUES[move.promotion]
        if board.gives_check(move):
            priority += 8_000
        return priority, move.uci()

    def _ordered_moves(self, board: chess.Board, tactical_only: bool) -> list[chess.Move]:
        moves = list(board.legal_moves)
        if tactical_only:
            moves = [
                move
                for move in moves
                if board.is_capture(move) or move.promotion is not None or board.gives_check(move)
            ]
        return sorted(moves, key=lambda move: self._move_priority(board, move), reverse=True)

    @staticmethod
    def _render_branch(
        board: chess.Board,
        score: int,
        move: chess.Move,
        pv: list[chess.Move],
    ) -> SearchBranch:
        line = [move, *pv]
        replay = board.copy(stack=False)
        san = []
        uci = []
        for item in line:
            if item not in replay.legal_moves:
                break
            san.append(replay.san(item))
            uci.append(item.uci())
            replay.push(item)
        return SearchBranch(
            move_uci=move.uci(),
            move_san=board.san(move),
            score_cp=score,
            principal_variation_uci=uci,
            principal_variation_san=san,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded deterministic chess state-action adapter.")
    parser.add_argument("--fen", required=True)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--quiescence-depth", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=250_000)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    args = parser.parse_args()
    result = ChessTreeSearch(
        SearchConfig(
            depth=args.depth,
            quiescence_depth=args.quiescence_depth,
            top_k=args.top_k,
            max_nodes=args.max_nodes,
            timeout_s=args.timeout_s,
        )
    ).search(chess.Board(args.fen))
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
