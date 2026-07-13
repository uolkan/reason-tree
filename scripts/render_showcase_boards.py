#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import chess
import chess.svg


CASES = {
    "grimshaw": {
        "fen": "8/B2K3Q/5p2/3k4/2p2P2/p6p/r7/b7 w - - 0 1",
        "move": "h7b1",
    },
    "underpromotion": {
        "fen": "6k1/5pPp/4pPQP/3pP3/2pP4/1pP5/pP5K/R7 w - - 0 1",
        "move": "g6b1",
    },
}


def render_case(name: str, fen: str, move_uci: str, output_dir: Path) -> None:
    board = chess.Board(fen)
    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves:
        raise ValueError(f"illegal showcase move for {name}: {move_uci}")

    output_dir.mkdir(parents=True, exist_ok=True)
    start = chess.svg.board(board=board, size=480, coordinates=True)
    (output_dir / f"{name}-start.svg").write_text(start, encoding="utf-8")

    board.push(move)
    after = chess.svg.board(board=board, lastmove=move, size=480, coordinates=True)
    (output_dir / f"{name}-qb1.svg").write_text(after, encoding="utf-8")


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "assets" / "chess"
    for name, case in CASES.items():
        render_case(name, case["fen"], case["move"], output_dir)


if __name__ == "__main__":
    main()
