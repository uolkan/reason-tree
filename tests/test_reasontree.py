import json
import tempfile
import unittest
from pathlib import Path

from reasontree.core import ReasonTreeConfig, ReasonTreeRunner
from reasontree.examples import ChessMateAdapter


class ReasonTreeTest(unittest.TestCase):
    def test_chess_demo_selects_forcing_first_move(self):
        result = ReasonTreeRunner(ChessMateAdapter(), ReasonTreeConfig(max_depth=4)).run()
        self.assertEqual(result.best_action, "Bxg5+")
        self.assertIn("Qf4#", "\n".join(result.trace))

    def test_budget_limits_are_enforced(self):
        with self.assertRaises(ValueError):
            ReasonTreeConfig(max_depth=6)
        with self.assertRaises(ValueError):
            ReasonTreeConfig(branch_width=6)

    def test_demo_runner_writes_trace_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "trace.jsonl"
            result = ReasonTreeRunner(ChessMateAdapter(), log_path=log_path).run()
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(result.best_action, "Bxg5+")
            self.assertIn("expand_node", {event["event"] for event in events})
            self.assertIn("add_child", {event["event"] for event in events})
            self.assertEqual(events[-1]["event"], "final")


if __name__ == "__main__":
    unittest.main()
