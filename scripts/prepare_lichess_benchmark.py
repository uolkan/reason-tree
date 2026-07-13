#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from reasontree.chess_benchmark import case_from_lichess_row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze a deterministic rated-puzzle manifest from a decompressed Lichess puzzle CSV stream."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rating-min", type=int, default=1800)
    parser.add_argument("--rating-max", type=int, default=2000)
    parser.add_argument("--max-rating-deviation", type=int, default=80)
    parser.add_argument("--min-popularity", type=int, default=85)
    parser.add_argument("--min-plays", type=int, default=200)
    parser.add_argument("--min-moves", type=int, default=3)
    parser.add_argument("--max-moves", type=int, default=7)
    parser.add_argument("--scan-qualifying", type=int, default=500)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--development-count", type=int, default=25)
    parser.add_argument("--source-last-modified", default="2026-07-01")
    args = parser.parse_args()

    qualifying = []
    for row in csv.DictReader(sys.stdin):
        moves = row["Moves"].split()
        if not (args.rating_min <= int(row["Rating"]) <= args.rating_max):
            continue
        if int(row["RatingDeviation"]) > args.max_rating_deviation:
            continue
        if int(row["Popularity"]) < args.min_popularity or int(row["NbPlays"]) < args.min_plays:
            continue
        if not (args.min_moves <= len(moves) <= args.max_moves):
            continue
        qualifying.append(case_from_lichess_row(row))
        if len(qualifying) >= args.scan_qualifying:
            break

    cases = sorted(qualifying, key=lambda case: (case.rating, case.puzzle_id))[: args.limit]
    development_count = min(args.development_count, len(cases))
    payload = {
        "schema_version": 1,
        "source": {
            "name": "Lichess open puzzle database",
            "url": "https://database.lichess.org/lichess_db_puzzle.csv.zst",
            "license": "CC0",
            "last_modified": args.source_last_modified,
        },
        "selection": {
            "rule": "sort the first qualifying source rows by (rating, puzzle_id), then keep the lowest-rated cases",
            "rating_min": args.rating_min,
            "rating_max": args.rating_max,
            "max_rating_deviation": args.max_rating_deviation,
            "min_popularity": args.min_popularity,
            "min_plays": args.min_plays,
            "solution_length_including_setup": [args.min_moves, args.max_moves],
            "qualifying_rows_scanned": len(qualifying),
            "case_limit": args.limit,
        },
        "generated_on": date.today().isoformat(),
        "split": {
            "rule": "first cases after frozen sort are development; remaining cases are untouched holdout",
            "development_case_ids": [case.puzzle_id for case in cases[:development_count]],
            "holdout_case_ids": [case.puzzle_id for case in cases[development_count:]],
        },
        "cases": [asdict(case) for case in cases],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
