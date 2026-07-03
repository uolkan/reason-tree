import json
import unittest

from reasontree.reasontree import ReasonTreeConfig, extract_json_object, parse_claude_json, run_reasontree


class FakeClient:
    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt, schema):
        self.calls += 1
        if "Critique the selected" in prompt:
            return {
                "valid": True,
                "confidence": 0.9,
                "failure_check": "B only fails if urgency dominates risk.",
                "concerns": [],
            }
        if self.calls == 1:
            return {
                "branches": [
                    {
                        "action": "A",
                        "next_state": "fast but risky",
                        "score": 2.0,
                        "terminal": True,
                        "rationale": "risk violates the goal",
                    },
                    {
                        "action": "B",
                        "next_state": "slower but safer",
                        "score": 7.0,
                        "terminal": False,
                        "rationale": "matches the risk objective",
                    },
                ]
            }
        return {
            "branches": [
                {
                    "action": "B1",
                    "next_state": "safe rollout with monitoring",
                    "score": 9.5,
                    "terminal": True,
                    "rationale": "adds monitoring to the safer option",
                }
            ]
        }


class DuplicateStateClient:
    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt, schema):
        self.calls += 1
        if "Current state:\nshared state" in prompt:
            return {
                "branches": [
                    {
                        "action": "finish",
                        "next_state": "verified answer",
                        "score": 1.0,
                        "terminal": True,
                        "rationale": "shared cached state reaches the answer",
                    }
                ]
            }
        return {
            "branches": [
                {
                    "action": "A",
                    "next_state": "shared state",
                    "score": 6.0,
                    "terminal": False,
                    "rationale": "first route reaches the shared state",
                },
                {
                    "action": "B",
                    "next_state": "shared state",
                    "score": 5.0,
                    "terminal": False,
                    "rationale": "second route reaches the shared state",
                },
            ]
        }


class ContextLedgerClient:
    def complete_json(self, prompt, schema):
        return {
            "branches": [
                {
                    "action": "ask for one missing number",
                    "next_state": "decision becomes grounded by the missing number",
                    "score": 8.0,
                    "terminal": True,
                    "rationale": "the unknown number controls the recommendation",
                    "facts_used": ["deadline is fixed"],
                    "assumptions_used": ["user prefers reversible actions"],
                    "beliefs_tested": ["the fastest path is not always the safest path"],
                    "node_notes": ["the tree should preserve the missing-number dependency"],
                }
            ]
        }


class ReasonTreeTest(unittest.TestCase):
    def test_reasontree_selects_best_first_action(self):
        result = run_reasontree(
            "Choose A or B. Minimize user-facing risk.",
            FakeClient(),
            ReasonTreeConfig(max_depth=2, branch_width=2, beam_width=1),
        )
        self.assertEqual(result["best_action"], "B")
        self.assertTrue(result["valid"])
        self.assertEqual(result["runner_up"], "A")
        self.assertEqual(result["path"][0]["action"], "B")
        self.assertEqual(result["path"][1]["action"], "B1")

    def test_parse_claude_structured_output(self):
        payload = {"structured_output": {"branches": []}}
        self.assertEqual(parse_claude_json(json.dumps(payload)), {"branches": []})

    def test_extract_markdown_json(self):
        self.assertEqual(extract_json_object("```json\n{\"a\": 1}\n```"), {"a": 1})

    def test_duplicate_states_reuse_expansion_cache(self):
        client = DuplicateStateClient()
        result = run_reasontree(
            "Pick a route, then finish from the shared state.",
            client,
            ReasonTreeConfig(max_depth=2, branch_width=2, beam_width=2, run_critic=False),
        )
        self.assertEqual(client.calls, 2)
        self.assertEqual(result["best_action"], "A")
        self.assertIn("failure_notes", result)

    def test_context_ledger_is_preserved_in_tree_synthesis(self):
        result = run_reasontree(
            "Choose whether to act now or ask for one missing number.",
            ContextLedgerClient(),
            ReasonTreeConfig(max_depth=1, branch_width=1, run_critic=False),
        )
        self.assertEqual(result["path"][0]["facts_used"], ["deadline is fixed"])
        self.assertEqual(result["tree_synthesis"]["selected_path_assumptions"], ["user prefers reversible actions"])
        self.assertEqual(
            result["tree_synthesis"]["selected_path_beliefs_tested"],
            ["the fastest path is not always the safest path"],
        )


if __name__ == "__main__":
    unittest.main()
