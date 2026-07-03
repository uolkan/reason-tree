from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


EXPAND_SCHEMA: dict[str, Any] = {
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
class EngineConfig:
    max_depth: int = 3
    branch_width: int = 3
    keep_paths: int = 2
    max_nodes: int = 48
    run_critic: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.max_depth <= 5:
            raise ValueError("max_depth must be between 1 and 5")
        if not 1 <= self.branch_width <= 5:
            raise ValueError("branch_width must be between 1 and 5")
        if not 1 <= self.keep_paths <= 5:
            raise ValueError("keep_paths must be between 1 and 5")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be at least 1")


@dataclass
class TreeNode:
    state: str
    parent: "TreeNode | None" = None
    action: str | None = None
    score: float = 0.0
    rationale: str = ""
    terminal: bool = False
    facts_used: list[str] = field(default_factory=list)
    assumptions_used: list[str] = field(default_factory=list)
    beliefs_tested: list[str] = field(default_factory=list)
    node_notes: list[str] = field(default_factory=list)
    children: list["TreeNode"] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return len(self.path()) - 1

    @property
    def path_score(self) -> float:
        scores = [node.score for node in self.path()[1:]]
        return sum(scores) / len(scores) if scores else 0.0

    def path(self) -> list["TreeNode"]:
        node: TreeNode | None = self
        path: list[TreeNode] = []
        while node is not None:
            path.append(node)
            node = node.parent
        return list(reversed(path))

    def path_payload(self) -> list[dict[str, Any]]:
        return [node_payload(node) for node in self.path()[1:]]


class ClaudeCliClient:
    def __init__(
        self,
        *,
        model: str = "sonnet",
        effort: str = "medium",
        tools: str = "",
        timeout_s: int = 180,
        max_budget_usd: float | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.tools = tools
        self.timeout_s = timeout_s
        self.max_budget_usd = max_budget_usd

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
            "--no-session-persistence",
        ]
        if self.tools != "default":
            cmd.extend(["--tools", self.tools])
        if self.max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

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


def run_reasontree(
    task: str,
    client: JsonClient,
    config: EngineConfig | None = None,
    trace_log: Path | None = None,
) -> dict[str, Any]:
    config = config or EngineConfig()
    root = TreeNode(state=task)
    frontier = [root]
    expanded: list[TreeNode] = []
    cache: dict[str, list[dict[str, Any]]] = {}

    if trace_log:
        trace_log.parent.mkdir(parents=True, exist_ok=True)
        trace_log.write_text("", encoding="utf-8")
    write_trace(trace_log, "start", task=task, config=config_payload(config))

    for depth in range(1, config.max_depth + 1):
        next_frontier: list[TreeNode] = []
        for node in frontier:
            if node.terminal or len(expanded) >= config.max_nodes:
                write_trace(trace_log, "skip_node", depth=depth, node=node_payload(node))
                continue

            key = cache_key(task, node, depth, config)
            if key in cache:
                branches = cache[key]
                write_trace(trace_log, "cache_hit", depth=depth, node=node_payload(node))
            else:
                write_trace(trace_log, "expand_node", depth=depth, node=node_payload(node))
                response = client.complete_json(expand_prompt(task, node, depth, config), EXPAND_SCHEMA)
                branches = list(response.get("branches", []))[: config.branch_width]
                cache[key] = branches
                write_trace(trace_log, "branches_received", depth=depth, branches=branches)

            for branch in branches:
                child = child_from_branch(node, branch)
                node.children.append(child)
                expanded.append(child)
                write_trace(trace_log, "add_child", depth=depth, child=node_payload(child))
                if not child.terminal:
                    next_frontier.append(child)
                if len(expanded) >= config.max_nodes:
                    break

        if not next_frontier:
            write_trace(trace_log, "stop_expansion", depth=depth, reason="no_expandable_frontier")
            break
        frontier = sorted(next_frontier, key=lambda node: (node.path_score, node.score), reverse=True)[
            : config.keep_paths
        ]
        write_trace(trace_log, "select_frontier", depth=depth, frontier=[node_payload(node) for node in frontier])

    if not expanded:
        raise RuntimeError("ReasonTree produced no branches")

    best = max(expanded, key=lambda node: (node.path_score, node.score, -node.depth))
    critic = run_critic(task, best, client, config)
    result = {
        "best_action": best.path()[1].action if best.depth else best.action,
        "path": best.path_payload(),
        "path_score": round(best.path_score, 4),
        "runner_up": runner_up(root, best),
        "tree_synthesis": tree_synthesis(root, best),
        "critic": critic,
        "config": config_payload(config),
    }
    write_trace(trace_log, "final", result=result)
    return result


def run_critic(task: str, best: TreeNode, client: JsonClient, config: EngineConfig) -> dict[str, Any]:
    if not config.run_critic:
        return {
            "valid": True,
            "confidence": min(1.0, best.path_score / 10.0),
            "failure_check": "critic disabled",
            "concerns": [],
        }
    return client.complete_json(critic_prompt(task, best), CRITIC_SCHEMA)


def child_from_branch(parent: TreeNode, branch: dict[str, Any]) -> TreeNode:
    return TreeNode(
        state=str(branch.get("next_state", "")),
        parent=parent,
        action=str(branch.get("action", "")),
        score=clip_score(float(branch.get("score", 0.0))),
        rationale=str(branch.get("rationale", "")),
        terminal=bool(branch.get("terminal", False)),
        facts_used=string_list(branch.get("facts_used")),
        assumptions_used=string_list(branch.get("assumptions_used")),
        beliefs_tested=string_list(branch.get("beliefs_tested")),
        node_notes=string_list(branch.get("node_notes")),
    )


def expand_prompt(task: str, node: TreeNode, depth: int, config: EngineConfig) -> str:
    return f"""You are ReasonTree's node expander.

Original task:
{task}

Current state:
{node.state}

Path so far:
{json.dumps(node.path_payload(), ensure_ascii=True)}

Search settings:
- current depth: {depth}
- max depth: {config.max_depth}
- candidate actions for this state: {config.branch_width}

Generate up to {config.branch_width} next branches.
Each branch must describe:
- action: the next candidate action
- next_state: what becomes true after taking it
- score: 0-10 against the original goal and constraints
- terminal: true only if the branch solves the task or clearly fails
- rationale: short reason for the score
- facts_used: factual inputs this branch relies on
- assumptions_used: assumptions, beliefs, or preferences this branch relies on
- beliefs_tested: assumptions this branch would test or falsify
- node_notes: what this node teaches the larger tree

Prefer diverse actions. Compare siblings directly. Return JSON only."""


def critic_prompt(task: str, node: TreeNode) -> str:
    return f"""Critique this ReasonTree path.

Original task:
{task}

Selected path:
{json.dumps(node.path_payload(), ensure_ascii=True)}

Return JSON with:
- valid: whether the selected path satisfies the task constraints
- confidence: 0.0 to 1.0
- failure_check: the main way this could be wrong
- concerns: concise concerns

Return JSON only."""


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


def runner_up(root: TreeNode, best: TreeNode) -> str | None:
    if best.depth == 0:
        return None
    best_first = best.path()[1].action
    alternatives = [child for child in root.children if child.action != best_first]
    if not alternatives:
        return None
    return max(alternatives, key=lambda node: best_leaf_score(node)).action


def best_leaf_score(node: TreeNode) -> float:
    leaves = walk_leaves(node)
    return max(leaf.path_score for leaf in leaves)


def walk_leaves(node: TreeNode) -> list[TreeNode]:
    if not node.children:
        return [node]
    leaves: list[TreeNode] = []
    for child in node.children:
        leaves.extend(walk_leaves(child))
    return leaves


def tree_synthesis(root: TreeNode, best: TreeNode) -> dict[str, Any]:
    selected = best.path()[1:]
    nodes = [node for node in walk_nodes(root) if node.parent is not None]
    return {
        "root_actions_considered": [child.action for child in root.children],
        "selected_path_facts": unique(item for node in selected for item in node.facts_used),
        "selected_path_assumptions": unique(item for node in selected for item in node.assumptions_used),
        "selected_path_beliefs_tested": unique(item for node in selected for item in node.beliefs_tested),
        "cross_tree_assumptions": unique(item for node in nodes for item in node.assumptions_used),
        "cross_tree_notes": [
            {"action": node.action, "notes": node.node_notes}
            for node in nodes
            if node.node_notes
        ][:12],
    }


def walk_nodes(node: TreeNode) -> list[TreeNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(walk_nodes(child))
    return nodes


def node_payload(node: TreeNode) -> dict[str, Any]:
    return {
        "depth": node.depth,
        "action": node.action,
        "state": node.state,
        "score": node.score,
        "path_score": node.path_score,
        "terminal": node.terminal,
        "rationale": node.rationale,
        "facts_used": node.facts_used,
        "assumptions_used": node.assumptions_used,
        "beliefs_tested": node.beliefs_tested,
        "node_notes": node.node_notes,
    }


def config_payload(config: EngineConfig) -> dict[str, Any]:
    return {
        "max_depth": config.max_depth,
        "branch_width": config.branch_width,
        "keep_paths": config.keep_paths,
        "max_nodes": config.max_nodes,
        "run_critic": config.run_critic,
    }


def cache_key(task: str, node: TreeNode, depth: int, config: EngineConfig) -> str:
    return json.dumps(
        {
            "task": task,
            "state": node.state,
            "depth": depth,
            "branch_width": config.branch_width,
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def clip_score(score: float) -> float:
    return max(0.0, min(10.0, score))


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def unique(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def write_trace(path: Path | None, event: str, **payload: Any) -> None:
    if not path:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def read_task(args: argparse.Namespace) -> str:
    if args.task_file:
        return Path(args.task_file).read_text(encoding="utf-8")
    if args.task:
        return args.task
    raise SystemExit("Provide --task or --task-file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ReasonTree with Claude Code print mode.")
    parser.add_argument("--task", help="Task text")
    parser.add_argument("--task-file", help="Path to a task prompt")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--branch-width", type=int, default=3)
    parser.add_argument("--keep-paths", type=int, default=2)
    parser.add_argument("--max-nodes", type=int, default=48)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--tools", default="", help='Claude tools to expose. Default "" disables tools.')
    parser.add_argument("--max-budget-usd", type=float, help="Optional print-mode spend guardrail.")
    parser.add_argument("--no-critic", action="store_true")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    parser.add_argument("--trace-log", type=Path, help="Optional JSONL trace log path")
    args = parser.parse_args()

    config = EngineConfig(
        max_depth=args.max_depth,
        branch_width=args.branch_width,
        keep_paths=args.keep_paths,
        max_nodes=args.max_nodes,
        run_critic=not args.no_critic,
    )
    client = ClaudeCliClient(
        model=args.model,
        effort=args.effort,
        tools=args.tools,
        timeout_s=args.timeout_s,
        max_budget_usd=args.max_budget_usd,
    )
    result = run_reasontree(read_task(args), client, config, trace_log=args.trace_log)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
