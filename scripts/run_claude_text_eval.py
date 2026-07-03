#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Claude -p text eval.")
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--budget", default="0.3")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--tools", default="")
    parser.add_argument("--safe-mode", action="store_true")
    args = parser.parse_args()

    cmd = [
        "claude",
        "-p",
        args.prompt.read_text(encoding="utf-8"),
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--tools",
        args.tools,
        "--output-format",
        "json",
        "--max-budget-usd",
        args.budget,
        "--no-session-persistence",
    ]
    if args.safe_mode:
        cmd.append("--safe-mode")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=args.timeout, text=True)
        args.out.write_text(output, encoding="utf-8")
        print(output)
    except subprocess.TimeoutExpired as exc:
        timeout_path = args.out.with_suffix(args.out.suffix + ".timeout.txt")
        timeout_path.write_text(exc.output or "TIMEOUT", encoding="utf-8")
        raise SystemExit(f"Timed out after {args.timeout}s; wrote {timeout_path}")
    except subprocess.CalledProcessError as exc:
        error_path = args.out.with_suffix(args.out.suffix + ".error.txt")
        error_path.write_text(exc.output or "", encoding="utf-8")
        raise SystemExit(exc.returncode)


if __name__ == "__main__":
    main()
