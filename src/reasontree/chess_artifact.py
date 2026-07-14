"""Build a navigable tree-artifact spec from the bounded chess adapter.

This is the chess producer for :mod:`reasontree.tree_artifact`. It runs the
deterministic ``ChessTreeSearch`` at the root, then re-runs a shallower search
from each top candidate's successor position so the opponent's strongest
replies become real, inspectable counter-branches — the same evidence the
controller used, exposed level by level instead of summarized away.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chess

from .chess_tree import MATE_SCORE, PIECE_VALUES, ChessTreeSearch, SearchConfig


def _material_cp(board: chess.Board, color: chess.Color) -> int:
    total = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES[piece.piece_type]
        total += value if piece.color == color else -value
    return total


def _is_mate_score(score: int) -> bool:
    return abs(score) >= MATE_SCORE - 200


def _score_label(score: int) -> str:
    if _is_mate_score(score):
        plies = MATE_SCORE - abs(score)
        moves = (plies + 1) // 2
        return f"#{moves}" if score > 0 else f"#-{moves}"
    return f"{score / 100:+.1f}"


def _line_note(board: chess.Board, line_san: list[str], line_uci: list[str], score: int) -> str:
    """Deterministic one-line branch thought derived from search facts only."""
    mover = board.turn
    replay = board.copy(stack=False)
    for raw in line_uci:
        move = chess.Move.from_uci(raw)
        if move not in replay.legal_moves:
            break
        replay.push(move)
    if _is_mate_score(score):
        if score > 0:
            return f"forces checkmate: every defense loses within {(MATE_SCORE - score + 1) // 2} moves"
        return f"gets mated: the opponent has a forced win in {(MATE_SCORE + score + 1) // 2} moves"
    delta = _material_cp(replay, mover) - _material_cp(board, mover)
    first = line_san[0] if line_san else ""
    if delta >= 250:
        return f"{first} wins material: up {delta / 100:.1f} pawns after the forced sequence"
    if delta >= 80:
        return f"{first} comes out ahead by {delta / 100:.1f} pawns once the line settles"
    if delta <= -250:
        return f"refuted: the strongest reply leaves this branch down {-delta / 100:.1f} pawns"
    if delta <= -80:
        return f"the opponent's best reply keeps this branch {-delta / 100:.1f} pawns worse"
    return "roughly level after best play on both sides"


def build_spec(
    fen: str,
    *,
    depth: int = 4,
    quiescence_depth: int = 3,
    root_candidates: int = 5,
    expanded_candidates: int = 3,
    replies_per_candidate: int = 3,
    max_nodes: int = 300_000,
    timeout_s: float = 12.0,
    title: str | None = None,
    task: str | None = None,
    raw_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    board = chess.Board(fen)
    root_search = ChessTreeSearch(
        SearchConfig(
            depth=depth,
            quiescence_depth=quiescence_depth,
            top_k=root_candidates,
            max_nodes=max_nodes,
            timeout_s=timeout_s,
        )
    ).search(board.copy(stack=False))
    if not root_search.branches:
        raise SystemExit("bounded search produced no complete root branch for this FEN")

    best_score = root_search.branches[0].score_cp
    nodes: list[dict[str, Any]] = []
    for index, branch in enumerate(root_search.branches):
        child_board = board.copy(stack=False)
        child_board.push(chess.Move.from_uci(branch.move_uci))
        if index == 0:
            verdict = "selected"
        elif _is_mate_score(-branch.score_cp) or branch.score_cp <= min(best_score - 300, -100):
            verdict = "refuted"
        else:
            verdict = "survives"
        node: dict[str, Any] = {
            "action": branch.move_san,
            "role": "candidate",
            "score": branch.score_cp,
            "score_label": _score_label(branch.score_cp),
            "verdict": verdict,
            "note": _line_note(board, branch.principal_variation_san, branch.principal_variation_uci, branch.score_cp),
            "line": branch.principal_variation_san,
            "children": [],
        }
        if index < expanded_candidates and not child_board.is_game_over():
            reply_search = ChessTreeSearch(
                SearchConfig(
                    depth=max(2, depth - 1),
                    quiescence_depth=quiescence_depth,
                    top_k=replies_per_candidate,
                    max_nodes=max_nodes // 3,
                    timeout_s=max(2.0, timeout_s / 3),
                )
            ).search(child_board.copy(stack=False))
            for reply in reply_search.branches:
                # reply.score_cp is from the opponent's perspective; negate for ours
                our_score = -reply.score_cp
                continuation = reply.principal_variation_san[1:3]
                child: dict[str, Any] = {
                    "action": reply.move_san,
                    "role": "reply",
                    "score": our_score,
                    "score_label": _score_label(our_score),
                    "verdict": "survives" if our_score >= -80 else "refuted",
                    "note": "opponent's candidate resistance, scored from our side",
                    "line": reply.principal_variation_san,
                    "children": (
                        [
                            {
                                "action": " ".join(continuation),
                                "role": "continuation",
                                "note": "our follow-up on this reply's principal variation",
                            }
                        ]
                        if continuation
                        else []
                    ),
                }
                node["children"].append(child)
        nodes.append(node)

    side = "White" if board.turn == chess.WHITE else "Black"
    spec: dict[str, Any] = {
        "eyebrow": "ReasonTree · bounded chess state-action search",
        "title": title or f"{side} to move: which branch survives?",
        "task": task
        or (
            f"{side} to find the single best move. The controller enumerates legal actions, plays each "
            "one on a real copied board, lets the opponent choose its strongest reply, and scores the "
            "outcome under a strict budget."
        ),
        "state": f"FEN: {fen}\n\n{board}",
        "budget": {
            "depth": depth,
            "max_nodes": max_nodes,
            "timeout_s": timeout_s,
            "nodes_used": root_search.nodes,
            "wall_seconds": root_search.wall_seconds,
            "completed_full_root": root_search.completed,
        },
        "selected_action": root_search.branches[0].move_san,
        "nodes": nodes,
        "footnote": (
            "Scores are centipawns from the mover's perspective; #N marks a forced mate in N. Branch notes "
            "are generated from search facts (terminal checks, material deltas), not from a language model. "
            "Reply branches come from a shallower re-search of each successor position."
        ),
    }
    if raw_trace:
        spec["raw_trace"] = raw_trace
    return spec


def raw_trace_from_probe(probe: dict[str, Any], *, max_excerpts: int = 7, excerpt_chars: int = 420) -> dict[str, Any]:
    """Convert a streamed probe capture into the artifact's raw-trace pane."""
    chunks = probe.get("chunks_timeline") or []
    excerpts: list[dict[str, Any]] = []
    if chunks:
        text_total = "".join(c["text"] for c in chunks)
        # sample evenly across the stream so the drift is visible start-to-end
        picks = [int(i * (len(chunks) - 1) / max(1, max_excerpts - 1)) for i in range(min(max_excerpts, len(chunks)))]
        seen = set()
        for pick in picks:
            if pick in seen:
                continue
            seen.add(pick)
            start = chunks[pick]
            gathered = ""
            j = pick
            while j < len(chunks) and len(gathered) < excerpt_chars:
                gathered += chunks[j]["text"]
                j += 1
            excerpts.append({"t": start["t"], "text": gathered.strip()})
        del text_total
    status = probe.get("status", "timeout")
    trace: dict[str, Any] = {
        "label": f"raw {probe.get('model', 'haiku')} — same prompt, no tree",
        "status": status,
        "wall_seconds": probe.get("wall_seconds"),
        "streamed_chars": probe.get("streamed_chars"),
        "output_tokens": (probe.get("usage") or {}).get("output_tokens"),
        "cost_usd": probe.get("total_cost_usd"),
        "excerpts": excerpts,
        "markers": [
            {"t": 30, "label": "the benchmark's 30s operational cap — nothing usable committed yet"}
        ],
        "unfinished": status != "completed" or not probe.get("predicted_uci"),
    }
    if probe.get("predicted_uci"):
        trace["final"] = {
            "predicted": probe["predicted_uci"],
            "expected": probe.get("expected_uci"),
            "correct": bool(probe.get("correct")),
            "wall_seconds": probe.get("wall_seconds"),
        }
    return trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the bounded chess search as a navigable HTML artifact.")
    parser.add_argument("--fen", required=True)
    parser.add_argument("--output", type=Path, required=True, help=".html output (or .json with --spec-only)")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--quiescence-depth", type=int, default=3)
    parser.add_argument("--root-candidates", type=int, default=5)
    parser.add_argument("--expanded-candidates", type=int, default=3)
    parser.add_argument("--replies-per-candidate", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=300_000)
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--title")
    parser.add_argument("--task")
    parser.add_argument("--raw-probe", type=Path, help="optional streamed probe JSON for the comparison pane")
    parser.add_argument("--spec-only", action="store_true", help="write the spec JSON instead of HTML")
    parser.add_argument("--fragment", action="store_true", help="emit an HTML body fragment")
    args = parser.parse_args()

    raw_trace = None
    if args.raw_probe:
        raw_trace = raw_trace_from_probe(json.loads(args.raw_probe.read_text(encoding="utf-8")))
    spec = build_spec(
        args.fen,
        depth=args.depth,
        quiescence_depth=args.quiescence_depth,
        root_candidates=args.root_candidates,
        expanded_candidates=args.expanded_candidates,
        replies_per_candidate=args.replies_per_candidate,
        max_nodes=args.max_nodes,
        timeout_s=args.timeout_s,
        title=args.title,
        task=args.task,
        raw_trace=raw_trace,
    )
    if args.spec_only:
        args.output.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        from .tree_artifact import render_page

        args.output.write_text(render_page(spec, fragment=args.fragment), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
