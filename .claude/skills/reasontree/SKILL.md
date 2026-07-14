---
name: reasontree
description: Use ReasonTree for calculations, comparisons, schedules, decisions, diagnoses, coding, research, or puzzles where a fast model may hide an assumption, overthink, or skip a check. Prefer an executable state-action adapter with bounded branches; otherwise compare a direct answer with a fact-compatible counterexample, run the cheapest real verifier, and label prompt-only branches unverified.
---

# ReasonTree

Use ReasonTree to turn a task into a small state-action search tree. The point is not longer reasoning. The point is bounded, externalized reasoning: fewer branches, executable state transitions when possible, explicit scoring, and a concise synthesis.

Choose the strongest available mode:

1. **Executable adapter:** define state, legal actions, transition, score/check, and a stop budget. Run the tree outside the model, then use the model once to explain the selected branch.
2. **Deterministic verifier:** compare a direct branch with a fact-compatible counterexample, run the real check, then explain the evidence.
3. **Prompt-only heuristic:** use two short branches only when transitions cannot be executed. Label the result `unverified`; model agreement is not verification.

Do not use it for simple Q&A, obvious one-step tasks, or cases where tree search would add fake rigor. If the model already used a reliable verifier and the answer is clear, stop instead of building a ceremonial tree.

## Everyday Default

- one fact ledger
- two parallel branches: direct and counterexample
- one verifier
- no demanded exact answer when two fact-compatible worlds disagree

Use the installed `reasontree-check` controller when a deterministic verifier adapter matches the task. Use `reasontree-chess-tree` for mechanically replayable chess states. Read `references/state-action-adapters.md` before creating another executable adapter. Use the deeper model tournament only for problems that remain unresolved and cannot be checked by a cheaper adapter.

## Method

1. Restate the goal in one sentence.
2. Build a context ledger:
   - facts
   - assumptions or beliefs
   - hard constraints
   - user preferences
   - unknowns
3. Define the current state.
4. If transitions are executable, define legal actions and apply them to real copied states. Let an adversary, test, or counter-branch choose the strongest reply.
5. Otherwise build a direct-solution branch and a fact-compatible counterexample branch.
6. Score siblings together. Separate authoritative terminal checks from heuristic scores.
7. Run a real verifier for mechanically checkable claims: tests, source checks, calculations, schemas, solvers, deadlines, risk limits, or user constraints. Do not mark a path verified because another model agrees.
8. If two fact-compatible branches imply different answers, label the task underdetermined and name the missing fact.
9. Reject a failed terminal claim, record the concrete failure, and continue only if another branch is necessary.
10. Stop at the node, time, cost, or evidence threshold. Escalate only when the bounded check remains unresolved.

Avoid repeatedly asking the same state again. Revisit only if new evidence or a verifier failure changes the state.
Keep node notes short. Prefer a compact tree with useful evidence over a long chain of unverified thoughts.

## Node Format

Use this internally for each branch:

```json
{
  "state": "what is currently true",
  "action": "candidate next step",
  "next_state": "what likely becomes true",
  "score": 0,
  "rationale": "why this branch is strong or weak",
  "facts_used": [],
  "assumptions_used": [],
  "beliefs_tested": [],
  "failure_modes": []
}
```

## Answer Format

For the everyday path, return a concise answer:

```text
Status: verified | underdetermined | unverified

Checked answer: ...

Evidence: what was actually calculated, executed, or checked

Hidden assumption: ...

Best next action: ...
```

If evidence is weak, say so. If no branch is good enough, return the best partial path and the missing information needed to decide.

For a verified result, state what was executed or checked. A heuristic tree result is not verified merely because its state transitions were executable; name the scorer and its limits. For an unverified result, use the word `unverified` explicitly.

Read `references/verification-patterns.md` when the task involves repeated signals, time zones, totals, code execution, or an underdetermined decision. Read `references/state-action-adapters.md` when the domain has enumerable actions or executable consequences. Use an installed controller when one matches.

## Visual Tree Artifacts (on request)

When the user asks to see, inspect, or share the reasoning tree, render it as a navigable HTML artifact instead of pasting a text dump. Every branch, counter-branch, score, and stop budget becomes an expandable node.

- Chess/state positions: `reasontree-chess-artifact --fen <FEN> --output tree.html` (add `--raw-probe capture.json` to embed a captured raw-model stream side by side).
- Any other adapter: emit the domain-neutral tree-spec JSON (see `reasontree/tree_artifact.py` docstring for the shape: nodes with `action`, `score`, `verdict`, `note`, `line`, `children`) and render with `reasontree-tree-artifact --spec spec.json --output tree.html`.
- Use `--fragment` when publishing through a host that wraps the page shell for you.

Keep artifact claims aligned with evidence: branch notes must come from search facts or be labeled unverified, and a raw-stream comparison pane must quote the captured stream verbatim.
