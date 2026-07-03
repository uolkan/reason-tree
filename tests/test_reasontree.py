import json
import tempfile
import unittest
from pathlib import Path

from reasontree.core import ReasonTreeConfig, ReasonTreeRunner
from reasontree.examples import ChessMateAdapter, PlanningAdapter


class ReasonTreeTest(unittest.TestCase):
    def test_chess_demo_selects_forcing_first_move(self):
        result = ReasonTreeRunner(ChessMateAdapter(), ReasonTreeConfig(max_depth=4)).run()
        self.assertEqual(result.best_action, "Bxg5+")
        self.assertIn("Qf4#", "\n".join(result.trace))

    def test_planning_demo_selects_reversible_pilot(self):
        result = ReasonTreeRunner(PlanningAdapter()).run()
        self.assertEqual(result.best_action, "run_reversible_pilot")
        self.assertIn("launch_pilot_with_rollback_and_review", "\n".join(result.trace))
        self.assertIn("asking for a narrower pilot looks weak", result.tree_synthesis["selected_path_beliefs_tested"])

    def test_budget_limits_are_enforced(self):
        with self.assertRaises(ValueError):
            ReasonTreeConfig(max_depth=6)
        with self.assertRaises(ValueError):
            ReasonTreeConfig(branch_width=6)

    def test_demo_runner_writes_trace_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "trace.jsonl"
            result = ReasonTreeRunner(PlanningAdapter(), log_path=log_path).run()
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(result.best_action, "run_reversible_pilot")
            self.assertIn("expand_node", {event["event"] for event in events})
            self.assertIn("add_child", {event["event"] for event in events})
            self.assertEqual(events[-1]["event"], "final")


if __name__ == "__main__":
    unittest.main()
