from __future__ import annotations

import unittest

from reasontree.chess_artifact import build_spec, raw_trace_from_probe
from reasontree.tree_artifact import render_page


class TreeArtifactTest(unittest.TestCase):
    def test_render_escapes_and_includes_nodes(self) -> None:
        spec = {
            "title": "Demo <script>alert(1)</script>",
            "task": "pick a branch",
            "selected_action": "A",
            "budget": {"depth": 2},
            "nodes": [
                {
                    "action": "A",
                    "score": 100,
                    "score_label": "+1.0",
                    "verdict": "selected",
                    "note": "wins & survives",
                    "line": ["A", "b"],
                    "children": [{"action": "b", "role": "reply", "score": -20, "verdict": "survives"}],
                },
                {"action": "B", "score": -300, "verdict": "refuted"},
            ],
        }
        html = render_page(spec)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("wins &amp; survives", html)
        self.assertIn("v-selected", html)
        self.assertIn("v-refuted", html)
        self.assertIn("Expand all", html)

    def test_fragment_mode_has_no_document_shell(self) -> None:
        html = render_page({"title": "t", "nodes": []}, fragment=True)
        self.assertNotIn("<!doctype", html.lower())
        self.assertNotIn("<body", html.lower())
        self.assertIn("<title>t</title>", html)


class ChessArtifactSpecTest(unittest.TestCase):
    def test_mate_in_two_spec_selects_unique_key_move(self) -> None:
        # Grimshaw interference: the unique mate-in-2 key move is the quiet Qb1.
        spec = build_spec(
            "8/B2K3Q/5p2/3k4/2p2P2/p6p/r7/b7 w - - 0 1",
            depth=4,
            root_candidates=4,
            expanded_candidates=1,
            replies_per_candidate=2,
            timeout_s=20.0,
        )
        self.assertEqual(spec["selected_action"], "Qb1")
        self.assertEqual(spec["nodes"][0]["verdict"], "selected")
        self.assertTrue(spec["nodes"][0]["score_label"].startswith("#"))
        self.assertGreaterEqual(len(spec["nodes"]), 2)
        html = render_page(spec)
        self.assertIn("Qb1", html)

    def test_raw_trace_sampling_marks_unfinished(self) -> None:
        probe = {
            "status": "timeout",
            "wall_seconds": 600.0,
            "streamed_chars": 999,
            "predicted_uci": "",
            "chunks_timeline": [{"t": float(i), "text": f"chunk{i} "} for i in range(40)],
        }
        trace = raw_trace_from_probe(probe, max_excerpts=4, excerpt_chars=20)
        self.assertTrue(trace["unfinished"])
        self.assertLessEqual(len(trace["excerpts"]), 4)
        self.assertEqual(trace["excerpts"][0]["t"], 0.0)


if __name__ == "__main__":
    unittest.main()
