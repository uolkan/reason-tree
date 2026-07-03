from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


EXPANSION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "branches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "next_state": {"type": "string"},
                    "score": {"type": "number"},
                    "terminal": {"type": "boolean"},
                    "rationale": {"type": "string"},
                    "facts_used": {"type": "array", "items": {"type": "string"}},
                    "assumptions_used": {"type": "array", "items": {"type": "string"}},
                    "beliefs_tested": {"type": "array", "items": {"type": "string"}},
                    "node_notes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action", "next_state", "score", "terminal", "rationale"],
            },
        }
    },
    "required": ["branches"],
}


CRITIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "confidence": {"type": "number"},
        "failure_check": {"type": "string"},
        "concerns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["valid", "confidence", "failure_check", "concerns"],
}


class JsonClient(Protocol):
    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ReasonTreeConfig:
    max_depth: int = 3
    branch_width: int = 3
    beam_width: int = 2
    max_nodes: int = 48
    run_critic: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.max_depth <= 5:
            raise ValueError("max_depth must be between 1 and 5")
        if not 1 <= self.branch_width <= 5:
            raise ValueError("branch_width must be between 1 and 5")
        if self.beam_width < 1:
            raise ValueError("beam_width must be at least 1")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be at least 1")


@dataclass
class ReasonTreeNode:
    state: str
    parent: "ReasonTreeNode | None" = None
    action: str | None = None
    score: float = 0.0
    rationale: str = ""
    terminal: bool = False
    facts_used: list[str] = field(default_factory=list)
    assumptions_used: list[str] = field(default_factory=list)
    beliefs_tested: list[str] = field(default_factory=list)
    node_notes: list[str] = field(default_factory=list)
    children: list["ReasonTreeNode"] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return len(self.path()) - 1

    @property
    def path_score(self) -> float:
        items = [node.score for node in self.path()[1:]]
        return sum(items) / len(items) if items else 0.0

    def path(self) -> list["ReasonTreeNode"]:
        cursor: ReasonTreeNode | None = self
        items: list[ReasonTreeNode] = []
        while cursor is not None:
            items.append(cursor)
            cursor = cursor.parent
        return list(reversed(items))

    def path_payload(self) -> list[dict[str, Any]]:
        payload = []
        for node in self.path()[1:]:
            item = {
                "depth": node.depth,
                "action": node.action,
                "state": node.state,
                "score": round(node.score, 4),
                "rationale": node.rationale,
            }
            if node.facts_used:
                item["facts_used"] = node.facts_used
            if node.assumptions_used:
                item["assumptions_used"] = node.assumptions_used
            if node.beliefs_tested:
                item["beliefs_tested"] = node.beliefs_tested
            if node.node_notes:
                item["node_notes"] = node.node_notes
            payload.append(item)
        return payload


class ClaudePrintClient:
    def __init__(
        self,
        *,
        model: str,
        effort: str,
        max_budget_usd: float,
        timeout_s: int,
        tools: str,
    ) -> None:
        self.model = model
        self.effort = effort
        self.max_budget_usd = max_budget_usd
        self.timeout_s = timeout_s
        self.tools = tools

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema),
            "--max-budget-usd",
            str(self.max_budget_usd),
            "--no-session-persistence",
        ]
        if self.tools != "default":
            cmd.extend(["--tools", self.tools])

        completed = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=self.timeout_s,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stdout.strip() or f"claude exited {completed.returncode}")
        return parse_claude_json(completed.stdout)


def parse_claude_json(output: str) -> dict[str, Any]:
    outer = json.loads(output)
    if isinstance(outer, dict) and isinstance(outer.get("structured_output"), dict):
        return outer["structured_output"]

    result = outer.get("result") if isinstance(outer, dict) else outer
    if isinstance(result, dict):
        return result
    if not isinstance(result, str):
        raise ValueError("Claude output did not contain a JSON result")
    return extract_json_object(result)


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    return json.loads(stripped)


def run_reasontree(
    task: str,
    client: JsonClient,
    config: ReasonTreeConfig,
    trace_log: Path | None = None,
) -> dict[str, Any]:
    root = ReasonTreeNode(state=task)
    frontier = [root]
    expanded: list[ReasonTreeNode] = []
    expansion_cache: dict[str, list[dict[str, Any]]] = {}
    failure_notes: list[str] = []
    if trace_log:
        trace_log.parent.mkdir(parents=True, exist_ok=True)
        trace_log.write_text("", encoding="utf-8")
    write_trace_event(
        trace_log,
        "start",
        task=task,
        config={
            "max_depth": config.max_depth,
            "branch_width": config.branch_width,
            "beam_width": config.beam_width,
            "max_nodes": config.max_nodes,
            "run_critic": config.run_critic,
        },
    )

    for depth in range(1, config.max_depth + 1):
        next_frontier: list[ReasonTreeNode] = []
        for node in frontier:
            if len(expanded) >= config.max_nodes or node.terminal:
                write_trace_event(
                    trace_log,
                    "skip_node",
                    depth=depth,
                    reason="terminal_or_budget",
                    node=node_payload(node),
                )
                continue
            cache_key = expansion_cache_key(task, node, config, depth, failure_notes)
            if cache_key in expansion_cache:
                branches = expansion_cache[cache_key]
                write_trace_event(
                    trace_log,
                    "cache_hit",
                    depth=depth,
                    node=node_payload(node),
                    branch_count=len(branches),
                )
            else:
                write_trace_event(trace_log, "expand_node", depth=depth, node=node_payload(node))
                response = client.complete_json(
                    expansion_prompt(task, node, config, depth, failure_notes),
                    EXPANSION_SCHEMA,
                )
                branches = response.get("branches", [])[: config.branch_width]
                expansion_cache[cache_key] = branches
                write_trace_event(
                    trace_log,
                    "branches_received",
                    depth=depth,
                    node=node_payload(node),
                    branches=branches,
                )

            if not branches:
                failure_notes.append(f"depth {depth}: no branches generated for state {node.state[:80]}")
                continue

            for branch in branches:
                child = ReasonTreeNode(
                    state=str(branch["next_state"]),
                    parent=node,
                    action=str(branch["action"]),
                    score=clip_score(float(branch["score"])),
                    rationale=str(branch["rationale"]),
                    terminal=bool(branch["terminal"]),
                    facts_used=string_list(branch.get("facts_used")),
                    assumptions_used=string_list(branch.get("assumptions_used")),
                    beliefs_tested=string_list(branch.get("beliefs_tested")),
                    node_notes=string_list(branch.get("node_notes")),
                )
                node.children.append(child)
                expanded.append(child)
                write_trace_event(
                    trace_log,
                    "add_child",
                    depth=depth,
                    parent=node_payload(node),
                    child=node_payload(child),
                )
                if not child.terminal:
                    next_frontier.append(child)
                if len(expanded) >= config.max_nodes:
                    break

        if not next_frontier:
            failure_notes.append(
                f"depth {depth}: no expandable branches remained; selecting the best scored leaf"
            )
            write_trace_event(
                trace_log,
                "stop_expansion",
                depth=depth,
                reason="no_expandable_frontier",
                failure_notes=failure_notes,
            )
            break
        frontier = top_k(next_frontier, config.beam_width)
        write_trace_event(
            trace_log,
            "select_frontier",
            depth=depth,
            frontier=[node_payload(node) for node in frontier],
        )

    if not expanded:
        raise RuntimeError("No branches were generated")

    best = max(expanded, key=lambda node: (node.path_score, node.score, -node.depth))
    runner_up = find_runner_up(root, best)
    critic = (
        client.complete_json(critic_prompt(task, best), CRITIC_SCHEMA)
        if config.run_critic
        else {
            "valid": True,
            "confidence": min(1.0, best.path_score / 10.0),
            "failure_check": "critic disabled",
            "concerns": [],
        }
    )
    if not critic.get("valid", False):
        failure_notes.append(f"critic rejected selected path: {critic.get('failure_check', '')}")
    for concern in critic.get("concerns", []):
        failure_notes.append(f"critic concern: {concern}")

    result = {
        "best_action": best.path()[1].action if best.depth else None,
        "confidence": round(float(critic.get("confidence", best.path_score)), 4),
        "path": best.path_payload(),
        "runner_up": runner_up,
        "failure_check": critic.get("failure_check", ""),
        "failure_notes": failure_notes,
        "tree_synthesis": tree_synthesis(root, best),
        "valid": bool(critic.get("valid", False)),
        "concerns": critic.get("concerns", []),
        "config": {
            "max_depth": config.max_depth,
            "branch_width": config.branch_width,
            "beam_width": config.beam_width,
            "max_nodes": config.max_nodes,
            "run_critic": config.run_critic,
        },
    }
    write_trace_event(trace_log, "final", result=result)
    return result


def expansion_cache_key(
    task: str,
    node: ReasonTreeNode,
    config: ReasonTreeConfig,
    depth: int,
    failure_notes: list[str],
) -> str:
    return json.dumps(
        {
            "task": task,
            "state": node.state,
            "depth": depth,
            "branch_width": config.branch_width,
            "failure_notes": failure_notes,
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def expansion_prompt(
    task: str,
    node: ReasonTreeNode,
    config: ReasonTreeConfig,
    depth: int,
    failure_notes: list[str] | None = None,
) -> str:
    return f"""You are running ReasonTree, a model-guided tree controller.

Task:
{task}

Current state:
{node.state}

Current path:
{json.dumps(node.path_payload(), ensure_ascii=True)}

Search settings:
- depth: {depth}
- max_depth: {config.max_depth}
- branch_width: {config.branch_width}

Failure notes from earlier search:
{json.dumps(failure_notes or [], ensure_ascii=True)}

Generate up to {config.branch_width} candidate next actions.
For each candidate:
- action: concise action or answer candidate
- next_state: expected state after taking the action
- score: number from 0.0 to 10.0 against the original task goal
- terminal: true only if this branch already solves or clearly fails the task
- rationale: one short evidence-based reason
- facts_used: factual inputs this branch relies on
- assumptions_used: assumptions, beliefs, preferences, or psychological premises this branch relies on
- beliefs_tested: beliefs or assumptions this branch would test or pressure
- node_notes: concise implications for the broader tree, not just this branch

Prefer diverse actions. Do not hide uncertainty. Return JSON only."""


def critic_prompt(task: str, node: ReasonTreeNode) -> str:
    return f"""Critique the selected ReasonTree path.

Original task:
{task}

Selected path:
{json.dumps(node.path_payload(), ensure_ascii=True)}

Check whether the selected first action actually satisfies the task.
Return:
- valid: whether the path satisfies the hard constraints
- confidence: number from 0.0 to 1.0
- failure_check: the most important reason this could be wrong
- concerns: short list of concerns

Return JSON only."""


def top_k(nodes: list[ReasonTreeNode], k: int) -> list[ReasonTreeNode]:
    return sorted(nodes, key=lambda node: (node.path_score, node.score), reverse=True)[:k]


def find_runner_up(root: ReasonTreeNode, best: ReasonTreeNode) -> str | None:
    if best.depth == 0:
        return None
    best_first = best.path()[1].action
    alternatives = [child for child in root.children if child.action != best_first]
    if not alternatives:
        return None
    return max(alternatives, key=lambda node: (best_descendant(node).path_score, node.score)).action


def best_descendant(node: ReasonTreeNode) -> ReasonTreeNode:
    cursor = node
    while cursor.children:
        cursor = max(cursor.children, key=lambda item: (item.path_score, item.score))
    return cursor


def tree_synthesis(root: ReasonTreeNode, best: ReasonTreeNode) -> dict[str, Any]:
    nodes = [node for node in walk_nodes(root) if node.parent is not None]
    selected = best.path()[1:]
    return {
        "root_actions_considered": [child.action for child in root.children],
        "selected_path_facts": unique_items(item for node in selected for item in node.facts_used),
        "selected_path_assumptions": unique_items(item for node in selected for item in node.assumptions_used),
        "selected_path_beliefs_tested": unique_items(item for node in selected for item in node.beliefs_tested),
        "cross_tree_assumptions": unique_items(item for node in nodes for item in node.assumptions_used),
        "cross_tree_beliefs_tested": unique_items(item for node in nodes for item in node.beliefs_tested),
        "notable_node_notes": [
            {"action": node.action, "notes": node.node_notes}
            for node in nodes
            if node.node_notes
        ][:12],
    }


def walk_nodes(node: ReasonTreeNode) -> list[ReasonTreeNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(walk_nodes(child))
    return nodes


def unique_items(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def clip_score(score: float) -> float:
    return max(0.0, min(10.0, score))


def node_payload(node: ReasonTreeNode) -> dict[str, Any]:
    return {
        "depth": node.depth,
        "state": node.state,
        "action": node.action,
        "score": node.score,
        "path_score": node.path_score,
        "terminal": node.terminal,
        "rationale": node.rationale,
        "facts_used": node.facts_used,
        "assumptions_used": node.assumptions_used,
        "beliefs_tested": node.beliefs_tested,
        "node_notes": node.node_notes,
    }


def write_trace_event(trace_log: Path | None, event: str, **payload: Any) -> None:
    if not trace_log:
        return
    with trace_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def read_task(args: argparse.Namespace) -> str:
    if args.task_file:
        return Path(args.task_file).read_text(encoding="utf-8")
    if args.task:
        return args.task
    raise SystemExit("Provide --task or --task-file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ReasonTree with Claude Code print mode.")
    parser.add_argument("--task", help="Task text to solve")
    parser.add_argument("--task-file", help="Path to a task prompt")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--branch-width", type=int, default=3)
    parser.add_argument("--beam-width", type=int, default=2)
    parser.add_argument("--max-nodes", type=int, default=48)
    parser.add_argument("--max-budget-usd", type=float, default=0.35)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--tools", default="", help='Claude tools to expose. Default "" disables tools; use "default" for defaults.')
    parser.add_argument("--no-critic", action="store_true")
    parser.add_argument("--print-first-prompt", action="store_true")
    parser.add_argument("--out", help="Optional JSON output path")
    parser.add_argument("--trace-log", type=Path, help="Optional JSONL trace log path")
    args = parser.parse_args()

    task = read_task(args)
    config = ReasonTreeConfig(
        max_depth=args.max_depth,
        branch_width=args.branch_width,
        beam_width=args.beam_width,
        max_nodes=args.max_nodes,
        run_critic=not args.no_critic,
    )

    if args.print_first_prompt:
        preview_node = ReasonTreeNode(state=task)
        print(expansion_prompt(task, preview_node, config, depth=1))
        return

    client = ClaudePrintClient(
        model=args.model,
        effort=args.effort,
        max_budget_usd=args.max_budget_usd,
        timeout_s=args.timeout_s,
        tools=args.tools,
    )
    result = run_reasontree(task, client, config, trace_log=args.trace_log)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
