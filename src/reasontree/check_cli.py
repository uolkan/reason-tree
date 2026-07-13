from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .verifiers import dependence_bounds


def verified_prompt(task: str, evidence: dict[str, Any] | None) -> str:
    evidence_text = json.dumps(evidence, indent=2, sort_keys=True) if evidence else "No deterministic adapter was selected."
    if evidence and evidence.get("identifiable") is False:
        output_rule = """Return exactly four bullet lines and no other text:
- Status: Underdetermined.
- Verified range: <minimum percent> to <maximum percent>.
- Independence scenario: <percent>, explicitly labeled unproven.
- Missing measurement: <the joint measurement needed>.
Do not explain or name which dependence pattern attains either extreme."""
    else:
        output_rule = "Return a concise answer that distinguishes verified evidence from assumptions."
    return f"""You are the explanation layer of ReasonTree Check.

ORIGINAL TASK:
{task}

REASON TREE:
- Branch A: answer under the conventional hidden assumption.
- Branch B: keep every stated fact fixed and challenge that assumption.

DETERMINISTIC VERIFIER EVIDENCE:
{evidence_text}

Rules:
1. Deterministic verifier evidence outranks model intuition.
2. If identifiable is false, begin the answer with "Underdetermined" and do not invent a point estimate.
3. Report posterior_bounds as the admissible range. Independence is one interior scenario; report independence_scenario only as a labeled scenario, never as an upper or lower bound.
4. Do not label an extreme as perfect correlation, moderate correlation, or another named dependence pattern unless the verifier evidence proves that label. Call it an admissible extreme.
5. A qualitative claim such as shared vendor does not quantify dependence.
6. State the missing measurement needed to identify one answer.
7. Keep the final answer concise and useful to a non-expert.

OUTPUT CONTRACT:
{output_rule}
"""


def run_claude(prompt: str, model: str, effort: str, timeout_s: int) -> dict[str, Any]:
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
    started = time.monotonic()
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or f"claude exited {completed.returncode}")
    payload = json.loads(completed.stdout)
    return {
        "answer": str(payload.get("result", "")).strip(),
        "wall_seconds": round(time.monotonic() - started, 3),
        "provider_metadata": {
            "duration_ms": payload.get("duration_ms"),
            "total_cost_usd_equivalent": payload.get("total_cost_usd"),
            "usage": payload.get("usage"),
            "model_usage": payload.get("modelUsage"),
        },
    }


def run_codex(prompt: str, model: str, effort: str, timeout_s: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="reasontree-codex-") as tmp:
        output_path = Path(tmp) / "answer.txt"
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
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stdout.strip() or f"codex exited {completed.returncode}")
        if not output_path.exists():
            raise RuntimeError("codex completed without writing a final answer")
        return {
            "answer": output_path.read_text(encoding="utf-8").strip(),
            "wall_seconds": round(time.monotonic() - started, 3),
            "provider_metadata": {"cli_output_available": bool(completed.stdout.strip())},
        }


def read_task(args: argparse.Namespace) -> str:
    if args.task_file:
        return Path(args.task_file).read_text(encoding="utf-8")
    if args.task:
        return args.task
    raise SystemExit("Provide --task or --task-file")


def load_case_file(args: argparse.Namespace) -> None:
    if not args.case_file:
        return
    payload = json.loads(Path(args.case_file).read_text(encoding="utf-8"))
    if not args.task and not args.task_file:
        args.task = payload.get("task")
    if args.verifier == "none" and payload.get("verifier"):
        args.verifier = payload["verifier"]
    for name, value in payload.get("verifier_args", {}).items():
        attribute = name.replace("-", "_")
        if hasattr(args, attribute) and getattr(args, attribute) is None:
            setattr(args, attribute, value)


def build_evidence(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.verifier == "none":
        return None
    required = {
        "prevalence": args.prevalence,
        "sensitivity_1": args.sensitivity_1,
        "sensitivity_2": args.sensitivity_2,
        "false_positive_1": args.false_positive_1,
        "false_positive_2": args.false_positive_2,
    }
    missing = [name.replace("_", "-") for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("dependence verifier requires: " + ", ".join("--" + name for name in missing))
    return dependence_bounds(**required)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a deterministic verifier, then explain the result through Claude or Codex subscription CLI."
    )
    parser.add_argument("--provider", required=True, choices=["claude", "codex"])
    parser.add_argument("--model", help="Provider model alias or id")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--task")
    parser.add_argument("--task-file")
    parser.add_argument("--case-file", help="JSON file containing task, verifier, and verifier_args")
    parser.add_argument("--verifier", default="none", choices=["none", "dependence"])
    parser.add_argument("--prevalence", type=float)
    parser.add_argument("--sensitivity-1", type=float)
    parser.add_argument("--sensitivity-2", type=float)
    parser.add_argument("--false-positive-1", type=float)
    parser.add_argument("--false-positive-2", type=float)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_case_file(args)
    task = read_task(args)
    evidence = build_evidence(args)
    prompt = verified_prompt(task, evidence)
    if args.dry_run:
        print(prompt)
        return

    if args.provider == "claude":
        model = args.model or "haiku"
        run = run_claude(prompt, model, args.effort, args.timeout_s)
    else:
        model = args.model or "gpt-5.6-luna"
        run = run_codex(prompt, model, args.effort, args.timeout_s)

    if args.json_output:
        print(json.dumps({"provider": args.provider, "model": model, "evidence": evidence, **run}, indent=2))
    else:
        print(run["answer"])
