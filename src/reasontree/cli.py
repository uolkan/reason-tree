from __future__ import annotations

import argparse
from pathlib import Path

from .core import ReasonTreeConfig, ReasonTreeRunner
from .examples import get_adapter
from .report import write_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ReasonTree demos.")
    parser.add_argument("demo", choices=["chess"], nargs="?", default="chess")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--width", type=int, default=3)
    parser.add_argument("--beam-width", type=int, default=2)
    parser.add_argument("--max-nodes", type=int, default=48)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--log", type=Path, help="Optional JSONL trace log path.")
    args = parser.parse_args()

    names = [args.demo]
    config = ReasonTreeConfig(
        max_depth=args.depth,
        branch_width=args.width,
        beam_width=args.beam_width,
        max_nodes=args.max_nodes,
    )
    results = []
    for name in names:
        results.append(ReasonTreeRunner(get_adapter(name), config, log_path=args.log).run())

    for result in results:
        print(f"\n== {result.problem} ==")
        print(f"Direct baseline: {result.direct_baseline}")
        print(f"Expected: {result.expected}")
        print(f"ReasonTree: {result.best_action} (avg={result.best_reward:.2f})")
        print("Trace:")
        for line in result.trace:
            print(f"- {line}")

    if args.html:
        write_html_report(results, args.html)
        print(f"\nWrote {args.html}")
    if args.log:
        print(f"Wrote trace log under {args.log.parent}")


if __name__ == "__main__":
    main()
