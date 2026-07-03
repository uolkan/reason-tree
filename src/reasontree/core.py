from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Branch:
    action: str
    next_state: str
    reward: float
    rationale: str
    terminal: bool = False
    facts_used: tuple[str, ...] = ()
    assumptions_used: tuple[str, ...] = ()
    beliefs_tested: tuple[str, ...] = ()
    node_notes: tuple[str, ...] = ()


class ProblemAdapter(Protocol):
    name: str
    root_state: str
    label: str

    def branches(self, state: str) -> list[Branch]:
        ...

    def direct_baseline(self) -> str:
        ...


@dataclass
class Node:
    state: str
    parent: "Node | None" = None
    action: str | None = None
    rationale: str = ""
    children: list["Node"] = field(default_factory=list)
    score: float = 0.0
    terminal: bool = False
    facts_used: tuple[str, ...] = ()
    assumptions_used: tuple[str, ...] = ()
    beliefs_tested: tuple[str, ...] = ()
    node_notes: tuple[str, ...] = ()

    def path(self) -> list["Node"]:
        cursor: Node | None = self
        path: list[Node] = []
        while cursor is not None:
            path.append(cursor)
            cursor = cursor.parent
        return list(reversed(path))


@dataclass(frozen=True)
class ReasonTreeConfig:
    max_depth: int = 3
    branch_width: int = 3
    beam_width: int = 2
    max_nodes: int = 48

    def __post_init__(self) -> None:
        if not 1 <= self.max_depth <= 5:
            raise ValueError("max_depth must be between 1 and 5")
        if not 1 <= self.branch_width <= 5:
            raise ValueError("branch_width must be between 1 and 5")
        if self.beam_width < 1:
            raise ValueError("beam_width must be at least 1")


@dataclass(frozen=True)
class SearchResult:
    problem: str
    direct_baseline: str
    expected: str
    best_action: str
    best_reward: float
    trace: list[str]
    mermaid: str
    tree_synthesis: dict[str, object]


class ReasonTreeRunner:
    def __init__(
        self,
        adapter: ProblemAdapter,
        config: ReasonTreeConfig | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or ReasonTreeConfig()
        self.root = Node(adapter.root_state)
        self._expanded_nodes = 0
        self.log_path = log_path
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("", encoding="utf-8")
        self._log(
            "start",
            problem=self.adapter.name,
            root_state=self.adapter.root_state,
            config={
                "max_depth": self.config.max_depth,
                "branch_width": self.config.branch_width,
                "beam_width": self.config.beam_width,
                "max_nodes": self.config.max_nodes,
            },
        )

    def run(self) -> SearchResult:
        frontier = [self.root]
        for depth in range(1, self.config.max_depth + 1):
            next_frontier: list[Node] = []
            for node in frontier:
                if node.terminal or self._expanded_nodes >= self.config.max_nodes:
                    self._log(
                        "skip_node",
                        depth=depth,
                        node=self._node_payload(node),
                        reason="terminal_or_budget",
                    )
                    continue
                self._log("expand_node", depth=depth, node=self._node_payload(node))
                next_frontier.extend(self._expand_all(node))
                if self._expanded_nodes >= self.config.max_nodes:
                    break
            if not next_frontier:
                self._log("stop_expansion", depth=depth, reason="no_expandable_frontier")
                break
            frontier = sorted(next_frontier, key=self._path_reward, reverse=True)[: self.config.beam_width]
            self._log(
                "select_frontier",
                depth=depth,
                frontier=[self._node_payload(node) for node in frontier],
            )

        leaves = self._leaves(self.root)
        best_leaf = max(leaves, key=lambda node: (self._path_reward(node), node.score))
        best = best_leaf.path()[1] if self._depth(best_leaf) else best_leaf
        synthesis = self._tree_synthesis(best_leaf)
        self._log(
            "final",
            best_leaf=self._node_payload(best_leaf),
            best_action=best.action,
            path=[self._node_payload(node) for node in best_leaf.path()[1:]],
            tree_synthesis=synthesis,
        )
        return SearchResult(
            problem=self.adapter.name,
            direct_baseline=self.adapter.direct_baseline(),
            expected=self.adapter.label,
            best_action=best.action or "",
            best_reward=self._path_reward(best_leaf),
            trace=self._format_trace(best_leaf),
            mermaid=self.to_mermaid(),
            tree_synthesis=synthesis,
        )

    def _expand_all(self, node: Node) -> list[Node]:
        if node.terminal:
            return []

        known = {child.action for child in node.children}
        added: list[Node] = []
        for branch in self.adapter.branches(node.state)[: self.config.branch_width]:
            if self._expanded_nodes >= self.config.max_nodes:
                break
            if branch.action not in known:
                child = self._add_child(node, branch)
                added.append(child)
                self._log(
                    "add_child",
                    parent=self._node_payload(node),
                    child=self._node_payload(child),
                    path_score=self._path_reward(child),
                )
        return [child for child in added if not child.terminal]

    def _add_child(self, parent: Node, branch: Branch) -> Node:
        child = Node(
            state=branch.next_state,
            parent=parent,
            action=branch.action,
            rationale=branch.rationale,
            terminal=branch.terminal,
            score=branch.reward,
            facts_used=branch.facts_used,
            assumptions_used=branch.assumptions_used,
            beliefs_tested=branch.beliefs_tested,
            node_notes=branch.node_notes,
        )
        parent.children.append(child)
        self._expanded_nodes += 1
        return child

    def _depth(self, node: Node) -> int:
        return len(node.path()) - 1

    def _leaves(self, node: Node) -> list[Node]:
        if not node.children:
            return [node]
        leaves: list[Node] = []
        for child in node.children:
            leaves.extend(self._leaves(child))
        return leaves

    def _path_reward(self, node: Node) -> float:
        rewards = [item.score for item in node.path()[1:]]
        return sum(rewards) / len(rewards) if rewards else 0.0

    def _format_trace(self, node: Node) -> list[str]:
        trace: list[str] = []
        for item in node.path()[1:]:
            suffix = ""
            if item.assumptions_used:
                suffix += f" {self._sentence('Assumptions: ' + ', '.join(item.assumptions_used))}"
            if item.node_notes:
                suffix += f" {self._sentence('Note: ' + ', '.join(item.node_notes))}"
            trace.append(f"{item.action}: score={item.score:.2f}, {item.rationale}{suffix}")
        return trace

    def _sentence(self, text: str) -> str:
        return text if text.endswith((".", "!", "?")) else f"{text}."

    def _tree_synthesis(self, best_leaf: Node) -> dict[str, object]:
        nodes = [node for node in self._walk(self.root) if node.parent is not None]
        selected = best_leaf.path()[1:]
        runner_up = self._runner_up(best_leaf)
        return {
            "selected_path_facts": self._unique(item for node in selected for item in node.facts_used),
            "selected_path_assumptions": self._unique(item for node in selected for item in node.assumptions_used),
            "selected_path_beliefs_tested": self._unique(item for node in selected for item in node.beliefs_tested),
            "cross_tree_assumptions": self._unique(item for node in nodes for item in node.assumptions_used),
            "cross_tree_notes": [
                {"action": node.action, "notes": list(node.node_notes)}
                for node in nodes
                if node.node_notes
            ][:8],
            "runner_up": runner_up.action if runner_up else None,
            "robust_takeaway": self._robust_takeaway(best_leaf, runner_up),
        }

    def _runner_up(self, best_leaf: Node) -> Node | None:
        if self._depth(best_leaf) == 0:
            return None
        best_first = best_leaf.path()[1].action
        alternatives = [child for child in self.root.children if child.action != best_first]
        if not alternatives:
            return None
        return max(alternatives, key=lambda node: (self._best_descendant(node), node.score))

    def _best_descendant(self, node: Node) -> float:
        leaves = self._leaves(node)
        return max(self._path_reward(leaf) for leaf in leaves)

    def _robust_takeaway(self, best_leaf: Node, runner_up: Node | None) -> str:
        best_first = best_leaf.path()[1].action if self._depth(best_leaf) else best_leaf.action
        if not runner_up:
            return f"{best_first} remains the strongest available path under the explored branches."
        return (
            f"{best_first} is the selected path; {runner_up.action} is the closest alternative. "
            "Use the runner-up if the selected path's assumptions fail."
        )

    def _walk(self, node: Node) -> list[Node]:
        nodes = [node]
        for child in node.children:
            nodes.extend(self._walk(child))
        return nodes

    def _unique(self, items) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _node_payload(self, node: Node) -> dict[str, object]:
        return {
            "depth": self._depth(node),
            "state": node.state,
            "action": node.action,
            "score": node.score,
            "path_score": self._path_reward(node),
            "terminal": node.terminal,
            "rationale": node.rationale,
            "facts_used": list(node.facts_used),
            "assumptions_used": list(node.assumptions_used),
            "beliefs_tested": list(node.beliefs_tested),
            "node_notes": list(node.node_notes),
        }

    def _log(self, event: str, **payload: object) -> None:
        if not self.log_path:
            return
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **payload}, ensure_ascii=False, sort_keys=True) + "\n")

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        ids: dict[int, str] = {}

        def node_id(node: Node) -> str:
            key = id(node)
            if key not in ids:
                ids[key] = f"N{len(ids)}"
            return ids[key]

        def label(node: Node) -> str:
            if node.parent is None:
                return "Problem"
            score = f"{node.score:.2f}"
            return f"{node.action}<br/>score {score}"

        def walk(node: Node) -> None:
            current_id = node_id(node)
            lines.append(f'  {current_id}["{label(node)}"]')
            for child in node.children:
                child_id = node_id(child)
                lines.append(f"  {current_id} --> {child_id}")
                walk(child)

        walk(self.root)
        return "\n".join(lines)
