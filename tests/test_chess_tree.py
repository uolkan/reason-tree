from __future__ import annotations

import unittest

import chess

from reasontree.chess_tree import ChessStateAdapter, ChessTreeSearch, SearchConfig
from reasontree.state_search import BoundedSearchConfig, BoundedStateSearch


class ChessTreeTest(unittest.TestCase):
    def test_search_finds_forced_mate(self):
        board = chess.Board("6k1/5pPp/4pPQP/3pP3/2pP4/1pP5/pP5K/R7 w - - 0 1")
        result = ChessTreeSearch(SearchConfig(depth=3, timeout_s=5)).search(board)
        self.assertTrue(result.completed)
        self.assertEqual(result.branches[0].move_uci, "g6b1")
        self.assertGreater(result.branches[0].score_cp, 90_000)

    def test_search_reports_budget_exhaustion(self):
        board = chess.Board()
        original_fen = board.fen()
        result = ChessTreeSearch(SearchConfig(depth=5, max_nodes=1, timeout_s=5)).search(board)
        self.assertFalse(result.completed)
        self.assertLessEqual(result.nodes, 2)
        self.assertEqual(board.fen(), original_fen)

    def test_chess_implements_generic_state_action_contract(self):
        board = chess.Board("6k1/5pPp/4pPQP/3pP3/2pP4/1pP5/pP5K/R7 w - - 0 1")
        result = BoundedStateSearch(
            ChessStateAdapter(),
            BoundedSearchConfig(depth=3, quiescence_depth=3, max_nodes=100_000, timeout_s=5),
        ).search(board)
        self.assertEqual(result.branches[0].action, "g6b1")


if __name__ == "__main__":
    unittest.main()
