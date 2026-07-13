from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

import chess

from reasontree.chess_benchmark import (
    _parse_structured_payload,
    benchmark_prompt,
    case_from_lichess_row,
    direct_failure_ids,
    legal_move_groups,
    run_tree_case,
    tree_explanation_prompt,
)


ROW = {
    "PuzzleId": "00143",
    "FEN": "r2q1rk1/5ppp/1np5/p1b5/2p1B3/P7/1P3PPP/R1BQ1RK1 b - - 1 17",
    "Moves": "d8f6 d1h5 h7h6 h5c5",
    "Rating": "1825",
    "RatingDeviation": "78",
    "Popularity": "91",
    "NbPlays": "2933",
    "Themes": "advantage middlegame short",
    "GameUrl": "https://lichess.org/jcuxlI63/black#34",
    "OpeningTags": "",
}


class ChessBenchmarkTest(unittest.TestCase):
    def test_lichess_setup_move_is_applied_before_expected_move(self):
        case = case_from_lichess_row(ROW)
        board = chess.Board(case.position_fen)

        self.assertEqual(case.setup_uci, "d8f6")
        self.assertEqual(case.expected_uci, "d1h5")
        self.assertIn(chess.Move.from_uci(case.expected_uci), board.legal_moves)
        self.assertEqual(case.expected_san, "Qh5")

    def test_prompts_do_not_leak_ground_truth(self):
        case = case_from_lichess_row(ROW)
        direct_prompt, _ = benchmark_prompt(case, "direct")
        direct_text_prompt, _ = benchmark_prompt(case, "direct-text")
        self.assertNotIn(case.expected_uci, direct_prompt)
        self.assertNotIn(case.expected_uci, direct_text_prompt)
        for condition in ("matched", "reasontree"):
            prompt, _ = benchmark_prompt(case, condition)
            # The move may appear once in the exhaustive legal-move list, but it
            # is never marked as the expected or preferred move.
            self.assertEqual(prompt.count(case.expected_uci), 1)
            self.assertNotIn("expected", prompt.lower())
            self.assertNotIn(case.puzzle_id, prompt)

    def test_legal_move_groups_partition_all_moves(self):
        case = case_from_lichess_row(ROW)
        board = chess.Board(case.position_fen)
        groups = legal_move_groups(board)
        self.assertEqual(sum(map(len, groups.values())), board.legal_moves.count())

    def test_structured_payload_parses_condition_specific_key(self):
        direct, direct_move = _parse_structured_payload(
            {"structured_output": {"move_uci": "D1H5", "confidence": 0.8}}, "direct"
        )
        tree, tree_move = _parse_structured_payload(
            {"structured_output": {"selected_move_uci": "d1h5", "branches": []}}, "reasontree"
        )
        self.assertEqual(direct["confidence"], 0.8)
        self.assertEqual(direct_move, "d1h5")
        self.assertEqual(tree_move, "d1h5")

    def test_tree_evidence_does_not_use_answer_key(self):
        case = case_from_lichess_row(ROW)
        result = run_tree_case(case, depth=2, quiescence_depth=1, top_k=2, max_nodes=10_000, timeout_s=2)
        prompt = tree_explanation_prompt(case, result["answer"])
        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn(case.puzzle_id, prompt)

    def test_frozen_manifest_solution_lines_are_legal(self):
        manifest_path = Path(__file__).parents[1] / "benchmarks/chess/lichess_1800_2000_v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            board = chess.Board(case["position_fen"])
            for raw_move in case["solution_uci"]:
                move = chess.Move.from_uci(raw_move)
                self.assertIn(move, board.legal_moves, case["puzzle_id"])
                board.push(move)

    def test_direct_failure_filter_accepts_plain_text_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.jsonl"
            path.write_text(
                json.dumps({"puzzle_id": "a", "condition": "direct-text", "correct": False}) + "\n"
                + json.dumps({"puzzle_id": "b", "condition": "direct-text", "correct": True}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(direct_failure_ids(path), {"a"})


if __name__ == "__main__":
    unittest.main()
