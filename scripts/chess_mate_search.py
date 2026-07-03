#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

import chess


def attacker_has_forced_mate(board: chess.Board, attacker: chess.Color, plies_left: int) -> bool:
    if board.is_checkmate():
        return board.turn != attacker
    if plies_left <= 0 or board.is_stalemate() or board.is_insufficient_material():
        return False

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return False

    if board.turn == attacker:
        for move in legal_moves:
            child = board.copy(stack=False)
            child.push(move)
            if attacker_has_forced_mate(child, attacker, plies_left - 1):
                return True
        return False

    for move in legal_moves:
        child = board.copy(stack=False)
        child.push(move)
        if not attacker_has_forced_mate(child, attacker, plies_left - 1):
            return False
    return True


def principal_variation(board: chess.Board, attacker: chess.Color, plies_left: int) -> list[str]:
    if board.is_checkmate() or plies_left <= 0:
        return []

    legal_moves = list(board.legal_moves)
    if board.turn == attacker:
        for move in legal_moves:
            child = board.copy(stack=False)
            san = board.san(move)
            child.push(move)
            if attacker_has_forced_mate(child, attacker, plies_left - 1):
                return [san] + principal_variation(child, attacker, plies_left - 1)
        return []

    # Pick the defender reply that leaves the longest visible line.
    best_line: list[str] = []
    for move in legal_moves:
        child = board.copy(stack=False)
        san = board.san(move)
        child.push(move)
        if attacker_has_forced_mate(child, attacker, plies_left - 1):
            line = [san] + principal_variation(child, attacker, plies_left - 1)
            if len(line) > len(best_line):
                best_line = line
    return best_line


def solve(fen: str, mate_in: int) -> dict:
    board = chess.Board(fen)
    attacker = board.turn
    plies = mate_in * 2 - 1
    solutions = []

    for move in board.legal_moves:
        child = board.copy(stack=False)
        san = board.san(move)
        child.push(move)
        if attacker_has_forced_mate(child, attacker, plies - 1):
            solutions.append(
                {
                    "move": san,
                    "uci": move.uci(),
                    "principal_variation": [san] + principal_variation(child, attacker, plies - 1),
                }
            )

    return {
        "fen": fen,
        "mate_in": mate_in,
        "side_to_move": "white" if attacker == chess.WHITE else "black",
        "solutions": solutions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Find forced mate first moves from a FEN.")
    parser.add_argument("--fen", required=True)
    parser.add_argument("--mate-in", required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(solve(args.fen, args.mate_in), indent=2))


if __name__ == "__main__":
    main()
