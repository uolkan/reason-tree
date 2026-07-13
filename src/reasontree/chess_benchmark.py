from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import chess

from .chess_tree import ChessTreeSearch, SearchConfig


DIRECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "move_uci": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["move_uci", "confidence"],
}

TREE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "branches": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "move_uci": {"type": "string"},
                    "best_reply_uci": {"type": "string"},
                    "continuation_uci": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 10},
                    "refutation": {"type": "string"},
                },
                "required": [
                    "move_uci",
                    "best_reply_uci",
                    "continuation_uci",
                    "score",
                    "refutation",
                ],
            },
        },
        "selected_move_uci": {"type": "string"},
        "selection_reason": {"type": "string"},
    },
    "required": ["branches", "selected_move_uci", "selection_reason"],
}

TREE_EXPLANATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "move_uci": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["move_uci", "explanation"],
}


@dataclass(frozen=True)
class PuzzleCase:
    puzzle_id: str
    rating: int
    rating_deviation: int
    popularity: int
    plays: int
    themes: list[str]
    source_fen: str
    setup_uci: str
    position_fen: str
    expected_uci: str
    expected_san: str
    solution_uci: list[str]
    game_url: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PuzzleCase":
        return cls(
            puzzle_id=str(value["puzzle_id"]),
            rating=int(value["rating"]),
            rating_deviation=int(value["rating_deviation"]),
            popularity=int(value["popularity"]),
            plays=int(value["plays"]),
            themes=list(value["themes"]),
            source_fen=str(value["source_fen"]),
            setup_uci=str(value["setup_uci"]),
            position_fen=str(value["position_fen"]),
            expected_uci=str(value["expected_uci"]),
            expected_san=str(value["expected_san"]),
            solution_uci=list(value["solution_uci"]),
            game_url=str(value["game_url"]),
        )


def case_from_lichess_row(row: dict[str, str]) -> PuzzleCase:
    moves = row["Moves"].split()
    if len(moves) < 2:
        raise ValueError("Lichess puzzle row must include a setup move and a solution move")

    board = chess.Board(row["FEN"])
    setup = chess.Move.from_uci(moves[0])
    if setup not in board.legal_moves:
        raise ValueError(f"illegal setup move {moves[0]} for {row['PuzzleId']}")
    board.push(setup)

    expected = chess.Move.from_uci(moves[1])
    if expected not in board.legal_moves:
        raise ValueError(f"illegal expected move {moves[1]} for {row['PuzzleId']}")
    expected_san = board.san(expected)
    replay = board.copy(stack=False)
    for raw_move in moves[1:]:
        move = chess.Move.from_uci(raw_move)
        if move not in replay.legal_moves:
            raise ValueError(f"illegal solution move {raw_move} for {row['PuzzleId']}")
        replay.push(move)

    return PuzzleCase(
        puzzle_id=row["PuzzleId"],
        rating=int(row["Rating"]),
        rating_deviation=int(row["RatingDeviation"]),
        popularity=int(row["Popularity"]),
        plays=int(row["NbPlays"]),
        themes=row["Themes"].split(),
        source_fen=row["FEN"],
        setup_uci=moves[0],
        position_fen=board.fen(),
        expected_uci=moves[1],
        expected_san=expected_san,
        solution_uci=moves[1:],
        game_url=row["GameUrl"],
    )


def piece_ledger(board: chess.Board) -> str:
    lines = []
    for color, label in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
        pieces = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == color:
                pieces.append(f"{piece.symbol().upper()}{chess.square_name(square)}")
        lines.append(f"{label}: " + " ".join(pieces))
    return "\n".join(lines)


def legal_move_groups(board: chess.Board) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"checks": [], "captures": [], "quiet": []}
    for move in board.legal_moves:
        rendered = f"{move.uci()} ({board.san(move)})"
        if board.gives_check(move):
            groups["checks"].append(rendered)
        elif board.is_capture(move):
            groups["captures"].append(rendered)
        else:
            groups["quiet"].append(rendered)
    for moves in groups.values():
        moves.sort()
    return groups


def raw_position(case: PuzzleCase) -> str:
    board = chess.Board(case.position_fen)
    return (
        f"FEN: {case.position_fen}\n"
        f"Side to move: {'White' if board.turn == chess.WHITE else 'Black'}\n"
        "Board (rank 8 to 1, file a to h):\n"
        f"{board}\n"
    )


def enriched_position(case: PuzzleCase) -> str:
    board = chess.Board(case.position_fen)
    groups = legal_move_groups(board)
    return (
        raw_position(case)
        + "Piece ledger:\n"
        + piece_ledger(board)
        + "\nLegal checks: "
        + (", ".join(groups["checks"]) or "none")
        + "\nLegal captures: "
        + (", ".join(groups["captures"]) or "none")
        + "\nOther legal moves: "
        + (", ".join(groups["quiet"]) or "none")
        + "\n"
    )


def benchmark_prompt(case: PuzzleCase, condition: str) -> tuple[str, dict[str, Any] | None]:
    if condition in {"direct", "direct-text"}:
        output_rule = (
            "Return only one UCI move and no other text."
            if condition == "direct-text"
            else "Return only the requested JSON; use UCI notation such as e2e4 or e7e8q."
        )
        return (
            "Solve this chess tactic without tools. The displayed position is already after the "
            "opponent's setup move. Find the single best move for the side to move. "
            + output_rule
            + "\n\n"
            + raw_position(case),
            None if condition == "direct-text" else DIRECT_SCHEMA,
        )

    if condition == "matched":
        return (
            "Solve this chess tactic without tools. The displayed position is already after the "
            "opponent's setup move. You are given a deterministic piece ledger and legal-move list. "
            "Find the single best move. Return only the requested JSON; use UCI notation.\n\n"
            + enriched_position(case),
            DIRECT_SCHEMA,
        )

    if condition != "reasontree":
        raise ValueError(f"unknown condition: {condition}")

    return (
        "Solve this chess tactic with a compact ReasonTree and without tools. The displayed position "
        "is already after the opponent's setup move. Use the deterministic ledger below.\n\n"
        "Build two or three candidate branches. For each branch, predict Black's or White's strongest "
        "reply, one continuation, and a concrete refutation or reason it survives. Compare sibling "
        "branches on one 0-10 scale. Checks are candidates, not automatic winners; include a quiet move "
        "when forcing moves fail. Select the branch that survives the strongest reply. Keep every field "
        "short and return only the requested JSON in UCI notation.\n\n"
        + enriched_position(case),
        TREE_SCHEMA,
    )


def tree_explanation_prompt(case: PuzzleCase, search_result: dict[str, Any]) -> str:
    branches = search_result["branches"]
    return (
        "You are the concise explanation layer for a bounded chess state-action search. The search "
        "enumerated legal states without access to the benchmark answer key. Its highest-scoring branch "
        "is the controller's selected move. Explain that branch in one short sentence. Deterministic "
        "search evidence outranks intuition: repeat the selected move exactly and do not substitute a "
        "different move. Return only the requested JSON.\n\n"
        + raw_position(case)
        + "Bounded search evidence:\n"
        + json.dumps(branches, indent=2)
    )


def _parse_structured_payload(payload: dict[str, Any], condition: str) -> tuple[dict[str, Any], str]:
    structured = payload.get("structured_output")
    if not isinstance(structured, dict):
        result = payload.get("result", "")
        if isinstance(result, dict):
            structured = result
        elif isinstance(result, str):
            try:
                structured = json.loads(result)
            except json.JSONDecodeError:
                structured = {}
        else:
            structured = {}

    key = "selected_move_uci" if condition == "reasontree" else "move_uci"
    predicted = str(structured.get(key, "")).strip().lower()
    if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", predicted):
        predicted = ""
    return structured, predicted


def run_claude_case(
    prompt: str,
    schema: dict[str, Any],
    condition: str,
    model: str,
    effort: str,
    timeout_s: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    command = [
        "claude",
        "--safe-mode",
        "-p",
        prompt,
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema, separators=(",", ":")),
        "--no-session-persistence",
        "--tools",
        "",
    ]
    env = os.environ.copy()
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_output_tokens)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "answer": {},
            "predicted_uci": "",
            "wall_seconds": round(time.monotonic() - started, 3),
            "provider_metadata": {},
            "error": str(exc),
        }

    wall_seconds = round(time.monotonic() - started, 3)
    if completed.returncode != 0:
        return {
            "status": "error",
            "answer": {},
            "predicted_uci": "",
            "wall_seconds": wall_seconds,
            "provider_metadata": {},
            "error": completed.stdout.strip(),
        }

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "answer": {},
            "predicted_uci": "",
            "wall_seconds": wall_seconds,
            "provider_metadata": {},
            "error": "Claude CLI returned non-JSON output",
        }

    answer, predicted = _parse_structured_payload(payload, condition)
    return {
        "status": "ok" if predicted else "invalid",
        "answer": answer,
        "predicted_uci": predicted,
        "wall_seconds": wall_seconds,
        "provider_metadata": {
            "duration_ms": payload.get("duration_ms"),
            "duration_api_ms": payload.get("duration_api_ms"),
            "total_cost_usd_equivalent": payload.get("total_cost_usd"),
            "usage": payload.get("usage"),
            "model_usage": payload.get("modelUsage"),
        },
    }


def run_claude_text_case(
    prompt: str,
    model: str,
    effort: str,
    timeout_s: int,
    max_output_tokens: int,
    max_budget_usd: float | None = None,
) -> dict[str, Any]:
    command = [
        "claude",
        "--safe-mode",
        "-p",
        prompt,
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--tools",
        "",
    ]
    if max_budget_usd is not None:
        command.extend(["--max-budget-usd", str(max_budget_usd)])
    env = os.environ.copy()
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_output_tokens)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "answer": "",
            "predicted_uci": "",
            "wall_seconds": round(time.monotonic() - started, 3),
            "provider_metadata": {},
            "error": str(exc),
        }

    wall_seconds = round(time.monotonic() - started, 3)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "answer": "",
            "predicted_uci": "",
            "wall_seconds": wall_seconds,
            "provider_metadata": {},
            "error": "Claude CLI returned non-JSON envelope",
        }
    answer = str(payload.get("result", "")).strip()
    moves = set(re.findall(r"(?<![a-z0-9])[a-h][1-8][a-h][1-8][qrbn]?(?![a-z0-9])", answer.lower()))
    predicted = next(iter(moves)) if len(moves) == 1 else ""
    status = "ok" if predicted else "invalid"
    if completed.returncode != 0:
        status = "budget_exhausted" if payload.get("subtype") == "error_max_budget_usd" else "error"
    return {
        "status": status,
        "answer": answer,
        "predicted_uci": predicted,
        "wall_seconds": wall_seconds,
        "provider_metadata": {
            "duration_ms": payload.get("duration_ms"),
            "duration_api_ms": payload.get("duration_api_ms"),
            "total_cost_usd_equivalent": payload.get("total_cost_usd"),
            "usage": payload.get("usage"),
            "model_usage": payload.get("modelUsage"),
        },
        **({"error": payload.get("errors") or completed.stdout.strip()} if completed.returncode != 0 else {}),
    }


def run_codex_case(
    prompt: str,
    condition: str,
    model: str,
    effort: str,
    timeout_s: int,
) -> dict[str, Any]:
    prompt += "\nReturn valid JSON only."
    with tempfile.TemporaryDirectory(prefix="reasontree-chess-") as tmp:
        output_path = Path(tmp) / "answer.json"
        command = [
            "codex",
            "-a",
            "never",
            "-s",
            "read-only",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "-C",
            tmp,
            "-m",
            model,
            "-c",
            f"model_reasoning_effort='{effort}'",
            "-o",
            str(output_path),
            prompt,
        ]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "timeout",
                "answer": {},
                "predicted_uci": "",
                "wall_seconds": round(time.monotonic() - started, 3),
                "provider_metadata": {},
                "error": str(exc),
            }
        wall_seconds = round(time.monotonic() - started, 3)
        if completed.returncode != 0 or not output_path.exists():
            return {
                "status": "error",
                "answer": {},
                "predicted_uci": "",
                "wall_seconds": wall_seconds,
                "provider_metadata": {},
                "error": completed.stdout.strip(),
            }
        raw = output_path.read_text(encoding="utf-8").strip()
        try:
            answer = json.loads(raw)
        except json.JSONDecodeError:
            answer = {}
        key = "selected_move_uci" if condition == "reasontree" else "move_uci"
        predicted = str(answer.get(key, "")).strip().lower()
        if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", predicted):
            predicted = ""
        token_match = re.search(r"tokens used\s*\n?\s*([0-9,]+)", completed.stdout, re.IGNORECASE)
        return {
            "status": "ok" if predicted else "invalid",
            "answer": answer,
            "predicted_uci": predicted,
            "wall_seconds": wall_seconds,
            "provider_metadata": {
                "total_tokens": int(token_match.group(1).replace(",", "")) if token_match else None,
            },
        }


def run_tree_case(
    case: PuzzleCase,
    depth: int,
    quiescence_depth: int,
    top_k: int,
    max_nodes: int,
    timeout_s: float,
) -> dict[str, Any]:
    result = ChessTreeSearch(
        SearchConfig(
            depth=depth,
            quiescence_depth=quiescence_depth,
            top_k=top_k,
            max_nodes=max_nodes,
            timeout_s=timeout_s,
        )
    ).search(chess.Board(case.position_fen))
    payload = asdict(result)
    predicted = result.branches[0].move_uci if result.branches else ""
    return {
        "status": "ok" if predicted else "error",
        "answer": payload,
        "predicted_uci": predicted,
        "wall_seconds": result.wall_seconds,
        "provider_metadata": {"search": payload},
        **({"error": "bounded tree produced no complete root branch"} if not predicted else {}),
    }


def load_manifest(path: Path) -> tuple[dict[str, Any], list[PuzzleCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, [PuzzleCase.from_dict(item) for item in payload["cases"]]


def load_completed_keys(paths: Iterable[Path]) -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            keys.add((row["puzzle_id"], row["provider"], row["model"], row["condition"]))
    return keys


def direct_failure_ids(path: Path) -> set[str]:
    failures = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("condition") in {"direct", "direct-text"} and not row.get("correct", False):
            failures.add(row["puzzle_id"])
    return failures


def execute_case(case: PuzzleCase, args: argparse.Namespace, model: str) -> dict[str, Any]:
    if args.condition in {"tree", "tree-explain"}:
        run = run_tree_case(
            case,
            args.tree_depth,
            args.tree_quiescence_depth,
            args.tree_top_k,
            args.tree_max_nodes,
            args.tree_timeout_s,
        )
    else:
        prompt, schema = benchmark_prompt(case, args.condition)

    if args.condition == "tree":
        return run
    if args.condition == "tree-explain":
        selected = run["predicted_uci"]
        search_wall = run["wall_seconds"]
        search_metadata = run["provider_metadata"]
        prompt = tree_explanation_prompt(case, run["answer"])
        if args.provider == "claude":
            explanation = run_claude_case(
                prompt,
                TREE_EXPLANATION_SCHEMA,
                args.condition,
                model,
                args.effort,
                args.timeout_s,
                args.max_output_tokens,
            )
        else:
            explanation = run_codex_case(prompt, args.condition, model, args.effort, args.timeout_s)
        model_move = explanation["predicted_uci"]
        return {
            **explanation,
            "status": explanation["status"] if selected else "error",
            "predicted_uci": selected,
            "wall_seconds": round(search_wall + explanation["wall_seconds"], 4),
            "provider_metadata": {
                **explanation["provider_metadata"],
                **search_metadata,
                "model_suggested_uci": model_move,
                "controller_overrode_model": bool(model_move and model_move != selected),
            },
        }
    if args.provider == "claude" and args.condition == "direct-text":
        return run_claude_text_case(
            prompt,
            model,
            args.effort,
            args.timeout_s,
            args.max_output_tokens,
            args.max_budget_usd,
        )
    if args.provider == "claude":
        if schema is None:
            raise RuntimeError("structured Claude condition requires a JSON schema")
        return run_claude_case(
            prompt,
            schema,
            args.condition,
            model,
            args.effort,
            args.timeout_s,
            args.max_output_tokens,
        )
    return run_codex_case(prompt, args.condition, model, args.effort, args.timeout_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen Lichess chess cases through direct or ReasonTree prompts.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["claude", "codex", "local"], default="claude")
    parser.add_argument("--model")
    parser.add_argument("--effort", default="low")
    parser.add_argument(
        "--condition",
        choices=["direct", "direct-text", "matched", "reasontree", "tree", "tree-explain"],
        required=True,
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--direct-results", type=Path, help="Run only puzzle IDs that failed in this direct result file.")
    parser.add_argument("--until-failures", type=int, help="Stop a direct run after this many wrong/invalid/timeout cases.")
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--max-output-tokens", type=int, default=1200)
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--tree-depth", type=int, default=4)
    parser.add_argument("--tree-quiescence-depth", type=int, default=3)
    parser.add_argument("--tree-top-k", type=int, default=3)
    parser.add_argument("--tree-max-nodes", type=int, default=300_000)
    parser.add_argument("--tree-timeout-s", type=float, default=12.0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    if args.until_failures and args.workers > 1:
        raise SystemExit("--until-failures requires --workers 1 so the stop rule is exact")

    manifest, cases = load_manifest(args.manifest)
    del manifest
    selected_ids = set(args.case_id)
    if args.direct_results:
        selected_ids.update(direct_failure_ids(args.direct_results))
    if selected_ids:
        cases = [case for case in cases if case.puzzle_id in selected_ids]
    if args.offset:
        cases = cases[args.offset :]
    if args.limit is not None:
        cases = cases[: args.limit]

    if args.condition == "tree":
        args.provider = "local"
    if args.provider == "local" and args.condition != "tree":
        raise SystemExit("--provider local is valid only with --condition tree")
    model = args.model or (
        "bounded-tree-v1"
        if args.provider == "local"
        else ("haiku" if args.provider == "claude" else "gpt-5.6-luna")
    )
    completed = set() if args.no_resume else load_completed_keys([args.output])
    cases = [
        case
        for case in cases
        if (case.puzzle_id, args.provider, model, args.condition) not in completed
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failures = 0

    def evaluated_cases() -> Iterable[tuple[PuzzleCase, dict[str, Any]]]:
        if args.workers <= 1:
            for case in cases:
                yield case, execute_case(case, args, model)
            return
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            runs = executor.map(lambda item: execute_case(item, args, model), cases)
            yield from zip(cases, runs)

    with args.output.open("a", encoding="utf-8") as handle:
        for case, run in evaluated_cases():
            correct = run["predicted_uci"] == case.expected_uci
            result = {
                "schema_version": 1,
                "puzzle_id": case.puzzle_id,
                "rating": case.rating,
                "provider": args.provider,
                "model": model,
                "effort": args.effort,
                "condition": args.condition,
                "expected_uci": case.expected_uci,
                "predicted_uci": run["predicted_uci"],
                "correct": correct,
                **run,
            }
            handle.write(json.dumps(result, sort_keys=True) + "\n")
            handle.flush()
            print(
                f"{case.puzzle_id} rating={case.rating} condition={args.condition} "
                f"predicted={run['predicted_uci'] or '-'} expected={case.expected_uci} "
                f"correct={correct} wall={run['wall_seconds']}s",
                flush=True,
            )
            if not correct:
                failures += 1
            if args.condition in {"direct", "direct-text"} and args.until_failures and failures >= args.until_failures:
                break


if __name__ == "__main__":
    main()
