import argparse
import json
import tempfile
import unittest
from pathlib import Path

from reasontree.check_cli import load_case_file, verified_prompt


class CheckCliTest(unittest.TestCase):
    def test_prompt_rejects_false_precision(self):
        prompt = verified_prompt(
            "Give one exact probability.",
            {
                "identifiable": False,
                "posterior_bounds": {"minimum": 0.1, "maximum": 0.9},
                "independence_scenario": 0.5,
            },
        )

        self.assertIn('begin the answer with "Underdetermined"', prompt)
        self.assertIn("Independence is one interior scenario", prompt)
        self.assertIn("Return exactly four bullet lines", prompt)

    def test_case_file_populates_task_and_verifier_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            path.write_text(
                json.dumps(
                    {
                        "task": "test task",
                        "verifier": "dependence",
                        "verifier_args": {"prevalence": 0.01},
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                case_file=str(path),
                task=None,
                task_file=None,
                verifier="none",
                prevalence=None,
            )
            load_case_file(args)

        self.assertEqual(args.task, "test task")
        self.assertEqual(args.verifier, "dependence")
        self.assertEqual(args.prevalence, 0.01)


if __name__ == "__main__":
    unittest.main()
