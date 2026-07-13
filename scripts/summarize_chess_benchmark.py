#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def model_metric(row: dict[str, Any], key: str) -> int | float | None:
    usages = row["provider_metadata"].get("model_usage") or {}
    if not usages:
        return None
    return next(iter(usages.values())).get(key)


def rounded(value: float) -> float:
    return round(value, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize the frozen ReasonTree chess holdout run.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--rescues", type=Path, required=True)
    parser.add_argument("--cost-probes", type=Path, required=True)
    parser.add_argument("--efficiency-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    direct = load_jsonl(args.direct)
    tree = load_jsonl(args.tree)
    rescues = load_jsonl(args.rescues)
    cost_probes = load_jsonl(args.cost_probes)
    efficiency = load_jsonl(args.efficiency_control)
    cases = {case["puzzle_id"]: case for case in manifest["cases"]}
    holdout_ids = manifest["split"]["holdout_case_ids"]
    direct_by_id = {row["puzzle_id"]: row for row in direct}
    tree_by_id = {row["puzzle_id"]: row for row in tree}

    if set(direct_by_id) != set(holdout_ids) or set(tree_by_id) != set(holdout_ids):
        raise SystemExit("direct and tree inputs must each cover the complete frozen holdout split")
    if {row["condition"] for row in direct} != {"direct-text"}:
        raise SystemExit("primary direct input must contain only direct-text rows")
    if {row["condition"] for row in tree} != {"tree"}:
        raise SystemExit("tree input must contain only local tree rows")

    pairs = []
    for puzzle_id in holdout_ids:
        direct_row = direct_by_id[puzzle_id]
        tree_row = tree_by_id[puzzle_id]
        search = tree_row["provider_metadata"]["search"]
        pairs.append(
            {
                "puzzle_id": puzzle_id,
                "rating": cases[puzzle_id]["rating"],
                "expected_uci": cases[puzzle_id]["expected_uci"],
                "direct_status": direct_row["status"],
                "direct_predicted_uci": direct_row["predicted_uci"],
                "direct_correct": direct_row["correct"],
                "direct_wall_seconds": direct_row["wall_seconds"],
                "tree_predicted_uci": tree_row["predicted_uci"],
                "tree_correct": tree_row["correct"],
                "tree_wall_seconds": tree_row["wall_seconds"],
                "tree_nodes": search["nodes"],
                "tree_completed_full_root": search["completed"],
            }
        )

    rescue_rows = []
    expected_rescue_ids = [
        row["puzzle_id"] for row in pairs if not row["direct_correct"] and row["tree_correct"]
    ][:10]
    if [row["puzzle_id"] for row in rescues] != expected_rescue_ids:
        raise SystemExit("rescue input must be the first ten paired direct failures/tree successes")
    if [row["puzzle_id"] for row in cost_probes] != expected_rescue_ids:
        raise SystemExit("cost probes must cover the same ordered ten rescue cases")
    for row in rescues:
        puzzle_id = row["puzzle_id"]
        if direct_by_id[puzzle_id]["correct"] or not tree_by_id[puzzle_id]["correct"] or not row["correct"]:
            raise SystemExit(f"{puzzle_id} is not a direct-failure/tree-success rescue")
        rescue_rows.append(
            {
                "puzzle_id": puzzle_id,
                "rating": cases[puzzle_id]["rating"],
                "expected_uci": cases[puzzle_id]["expected_uci"],
                "direct_status": direct_by_id[puzzle_id]["status"],
                "tree_plus_haiku_wall_seconds": row["wall_seconds"],
                "tree_plus_haiku_cost_usd_equivalent": row["provider_metadata"]["total_cost_usd_equivalent"],
                "haiku_output_tokens": model_metric(row, "outputTokens"),
                "model_repeated_controller_move": not row["provider_metadata"]["controller_overrode_model"],
            }
        )

    control = efficiency[0]
    control_direct = direct_by_id[control["puzzle_id"]]
    if not control["correct"] or not control_direct["correct"]:
        raise SystemExit("efficiency control requires a case completed correctly by both conditions")
    direct_correct = sum(row["correct"] for row in direct)
    tree_correct = sum(row["correct"] for row in tree)
    direct_times = [row["wall_seconds"] for row in direct]
    tree_times = [row["wall_seconds"] for row in tree]
    rescue_times = [row["wall_seconds"] for row in rescues]
    rescue_costs = [row["provider_metadata"]["total_cost_usd_equivalent"] for row in rescues]
    rescue_tokens = [model_metric(row, "outputTokens") or 0 for row in rescues]
    rescue_by_id = {row["puzzle_id"]: row for row in rescues}
    cost_covered = [
        row for row in cost_probes if row["provider_metadata"].get("total_cost_usd_equivalent") is not None
    ]
    cost_probe_cases = []
    for row in cost_probes:
        matched = rescue_by_id[row["puzzle_id"]]
        cost_probe_cases.append(
            {
                "puzzle_id": row["puzzle_id"],
                "raw_status": row["status"],
                "raw_wall_seconds": row["wall_seconds"],
                "raw_cost_usd_equivalent": row["provider_metadata"].get("total_cost_usd_equivalent"),
                "raw_output_tokens": model_metric(row, "outputTokens"),
                "tree_plus_haiku_wall_seconds": matched["wall_seconds"],
                "tree_plus_haiku_cost_usd_equivalent": matched["provider_metadata"]["total_cost_usd_equivalent"],
                "tree_plus_haiku_output_tokens": model_metric(matched, "outputTokens"),
            }
        )
    covered_tree_rows = [rescue_by_id[row["puzzle_id"]] for row in cost_covered]
    covered_raw_cost = sum(row["provider_metadata"]["total_cost_usd_equivalent"] for row in cost_covered)
    covered_tree_cost = sum(row["provider_metadata"]["total_cost_usd_equivalent"] for row in covered_tree_rows)
    covered_raw_tokens = sum(model_metric(row, "outputTokens") or 0 for row in cost_covered)
    covered_tree_tokens = sum(model_metric(row, "outputTokens") or 0 for row in covered_tree_rows)
    covered_raw_wall = sum(row["wall_seconds"] for row in cost_covered)
    covered_tree_wall = sum(row["wall_seconds"] for row in covered_tree_rows)

    payload = {
        "schema_version": 1,
        "run_date": "2026-07-13",
        "protocol": {
            "source": manifest["source"],
            "selection": manifest["selection"],
            "split": {"development_cases": 25, "holdout_cases": 25},
            "primary_model_alias": "haiku",
            "resolved_model": "claude-haiku-4-5-20251001",
            "claude_cli_version": "2.1.207",
            "direct": {
                "condition": "direct-text",
                "tools": "disabled",
                "effort": "low",
                "wall_timeout_seconds": 30,
                "requested_output": "one UCI move",
            },
            "bounded_tree": {
                "depth": 4,
                "quiescence_depth": 3,
                "top_k": 3,
                "max_nodes": 300000,
                "wall_timeout_seconds": 12,
                "answer_key_available_during_search": False,
            },
        },
        "holdout": {
            "direct_correct": direct_correct,
            "direct_total": len(direct),
            "direct_accuracy": rounded(direct_correct / len(direct)),
            "direct_timeouts": sum(row["status"] == "timeout" for row in direct),
            "direct_mean_wall_seconds": rounded(statistics.mean(direct_times)),
            "direct_median_wall_seconds": rounded(statistics.median(direct_times)),
            "tree_correct": tree_correct,
            "tree_total": len(tree),
            "tree_accuracy": rounded(tree_correct / len(tree)),
            "tree_mean_wall_seconds": rounded(statistics.mean(tree_times)),
            "tree_median_wall_seconds": rounded(statistics.median(tree_times)),
            "accuracy_difference_percentage_points": rounded(100 * (tree_correct - direct_correct) / len(tree)),
            "paired_counts": {
                "both_correct": sum(row["direct_correct"] and row["tree_correct"] for row in pairs),
                "direct_only": sum(row["direct_correct"] and not row["tree_correct"] for row in pairs),
                "tree_only": sum(not row["direct_correct"] and row["tree_correct"] for row in pairs),
                "both_failed": sum(not row["direct_correct"] and not row["tree_correct"] for row in pairs),
            },
            "cases": pairs,
        },
        "ten_case_rescue_showcase": {
            "selection_rule": "first ten holdout cases in frozen order where direct-text failed and bounded-tree succeeded",
            "correct": sum(row["correct"] for row in rescues),
            "total": len(rescues),
            "mean_wall_seconds": rounded(statistics.mean(rescue_times)),
            "median_wall_seconds": rounded(statistics.median(rescue_times)),
            "min_wall_seconds": min(rescue_times),
            "max_wall_seconds": max(rescue_times),
            "total_cost_usd_equivalent": rounded(sum(rescue_costs)),
            "mean_cost_usd_equivalent": rounded(statistics.mean(rescue_costs)),
            "total_haiku_output_tokens": sum(rescue_tokens),
            "mean_haiku_output_tokens": rounded(statistics.mean(rescue_tokens)),
            "cases": rescue_rows,
            "long_run_raw_cost_probe": {
                "purpose": "separate telemetry trials; not additional holdout accuracy trials",
                "raw_trials": len(cost_probes),
                "raw_usable_answers": sum(bool(row["predicted_uci"]) for row in cost_probes),
                "raw_mean_wall_seconds": rounded(statistics.mean(row["wall_seconds"] for row in cost_probes)),
                "raw_min_wall_seconds": min(row["wall_seconds"] for row in cost_probes),
                "raw_max_wall_seconds": max(row["wall_seconds"] for row in cost_probes),
                "final_cost_metadata_coverage": len(cost_covered),
                "external_timeouts_without_cost_metadata": len(cost_probes) - len(cost_covered),
                "matched_covered_cases": {
                    "count": len(cost_covered),
                    "raw_total_cost_usd_equivalent": rounded(covered_raw_cost),
                    "tree_plus_haiku_total_cost_usd_equivalent": rounded(covered_tree_cost),
                    "raw_over_tree_cost_ratio": rounded(covered_raw_cost / covered_tree_cost),
                    "raw_total_output_tokens": covered_raw_tokens,
                    "tree_plus_haiku_total_output_tokens": covered_tree_tokens,
                    "raw_over_tree_output_token_ratio": rounded(covered_raw_tokens / covered_tree_tokens),
                    "raw_total_wall_seconds": rounded(covered_raw_wall),
                    "tree_plus_haiku_total_wall_seconds": rounded(covered_tree_wall),
                    "raw_over_tree_wall_ratio": rounded(covered_raw_wall / covered_tree_wall),
                },
                "cases": cost_probe_cases,
            },
        },
        "completed_case_efficiency_control": {
            "puzzle_id": control["puzzle_id"],
            "both_correct": bool(control["correct"] and control_direct["correct"]),
            "direct_wall_seconds": control_direct["wall_seconds"],
            "tree_plus_haiku_wall_seconds": control["wall_seconds"],
            "direct_cost_usd_equivalent": control_direct["provider_metadata"]["total_cost_usd_equivalent"],
            "tree_plus_haiku_cost_usd_equivalent": control["provider_metadata"]["total_cost_usd_equivalent"],
            "direct_output_tokens": model_metric(control_direct, "outputTokens"),
            "tree_plus_haiku_output_tokens": model_metric(control, "outputTokens"),
        },
        "limitations": [
            "The 25-case holdout is small and comes from one narrow 1809-1819 Lichess rating slice.",
            "A 30-second operational cap measures usable-answer latency, not whether Haiku might solve a case eventually.",
            "Only six of ten long-run raw cost probes emitted final cost metadata; the matched cost ratio applies to those six, not all ten.",
            "The ten-case showcase is selected from the full holdout after paired scoring; use the 1/25 versus 21/25 result for the unbiased comparison.",
            "The bounded evaluator is a small chess-specific state adapter, not evidence of universal reasoning uplift.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
