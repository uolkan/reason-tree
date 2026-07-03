import json
import tempfile
import unittest
from pathlib import Path

from reasontree.engine import EngineConfig, run_reasontree


class FakeClient:
    def complete_json(self, prompt, schema):
        if "Critique this ReasonTree path" in prompt:
            return {
                "valid": True,
                "confidence": 0.9,
                "failure_check": "assumption could be wrong",
                "concerns": [],
            }
        if "Current state:\nroot decision" in prompt:
            return {
                "branches": [
                    {
                        "action": "fast_launch",
                        "next_state": "risky path",
                        "score": 4,
                        "terminal": True,
                        "rationale": "fast but brittle",
                        "facts_used": ["deadline is close"],
                        "assumptions_used": ["speed is everything"],
                        "beliefs_tested": ["visibility matters most"],
                        "node_notes": ["weak downside control"],
                    },
                    {
                        "action": "small_pilot",
                        "next_state": "pilot path",
                        "score": 8,
                        "terminal": False,
                        "rationale": "keeps learning and rollback",
                        "facts_used": ["rollback is easy"],
                        "assumptions_used": ["small sample is useful"],
                        "beliefs_tested": ["pilot looks weak"],
                        "node_notes": ["best reversible path"],
                    },
                ]
            }
        return {
            "branches": [
                {
                    "action": "review_pilot",
                    "next_state": "pilot reviewed",
                    "score": 9,
                    "terminal": True,
                    "rationale": "turns action into learning",
                    "facts_used": ["rollback is easy"],
                    "assumptions_used": ["review will happen"],
                    "beliefs_tested": ["learning beats theater"],
                    "node_notes": ["recommended path"],
                }
            ]
        }


class EngineTest(unittest.TestCase):
    def test_engine_selects_best_first_action_and_synthesizes_context(self):
        result = run_reasontree(
            "root decision",
            FakeClient(),
            EngineConfig(max_depth=2, branch_width=2, keep_paths=1),
        )

        self.assertEqual(result["best_action"], "small_pilot")
        self.assertEqual(result["path"][-1]["action"], "review_pilot")
        self.assertIn("rollback is easy", result["tree_synthesis"]["selected_path_facts"])
        self.assertIn("pilot looks weak", result["tree_synthesis"]["selected_path_beliefs_tested"])

    def test_engine_writes_trace_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            run_reasontree(
                "root decision",
                FakeClient(),
                EngineConfig(max_depth=1, branch_width=2, keep_paths=1, run_critic=False),
                trace_log=trace_path,
            )
            events = [json.loads(line)["event"] for line in trace_path.read_text(encoding="utf-8").splitlines()]

        self.assertIn("expand_node", events)
        self.assertIn("add_child", events)
        self.assertEqual(events[-1], "final")


if __name__ == "__main__":
    unittest.main()
