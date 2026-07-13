from __future__ import annotations

import unittest

from reasontree.state_search import BoundedSearchConfig, BoundedStateSearch, MATE_SCORE


class TakeAwayAdapter:
    """Players remove one or two stones; taking the last stone wins."""

    def actions(self, state: int, *, tactical_only: bool) -> list[int]:
        del tactical_only
        return list(range(1, min(2, state) + 1))

    def transition(self, state: int, action: int) -> int:
        return state - action

    def terminal_score(self, state: int, ply: int) -> int | None:
        return -MATE_SCORE + ply if state == 0 else None

    def heuristic_score(self, state: int) -> int:
        return 0

    def action_id(self, action: int) -> str:
        return str(action)


class StateSearchTest(unittest.TestCase):
    def test_generic_adapter_finds_winning_action(self):
        result = BoundedStateSearch(
            TakeAwayAdapter(),
            BoundedSearchConfig(depth=4, top_k=2, max_nodes=100, timeout_s=1),
        ).search(4)
        self.assertTrue(result.completed)
        self.assertEqual(result.branches[0].action, "1")
        self.assertGreater(result.branches[0].score, 90_000)


if __name__ == "__main__":
    unittest.main()
