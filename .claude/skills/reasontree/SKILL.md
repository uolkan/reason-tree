---
description: Use ReasonTree for multi-step problems where a one-shot answer is brittle and several candidate paths should be compared before committing.
---

# ReasonTree

Use ReasonTree to turn a task into a small state-action search tree.

## When To Use

Use this skill when:

- there are 2-5 plausible next actions
- the user needs a decision, plan, diagnosis, repair, or synthesis
- assumptions or tradeoffs matter
- candidate paths can be scored, checked, or compared

Do not use it for simple Q&A, obvious one-step tasks, or cases where tree search would add fake rigor.

## Defaults

- depth: 3 levels
- actions per state: 3
- keep top paths per level: 2
- max depth: 5
- max actions per state: 5

## Method

1. Restate the goal in one sentence.
2. Build a context ledger:
   - facts
   - assumptions or beliefs
   - hard constraints
   - user preferences
   - unknowns
3. Define the current state.
4. Generate 3 candidate actions.
5. For each action, describe the next state.
6. Score sibling next states together on a 0-10 scale.
7. Keep the strongest 1-2 paths, plus one diverse path if uncertainty is high.
8. Expand selected paths until depth 3 or until a good enough answer is found.
9. Use any available verifier: tests, source checks, calculations, schemas, deadlines, risk limits, or user constraints.
10. Critique the selected path before answering.

Avoid repeatedly asking the same state again. Revisit only if new evidence or a verifier failure changes the state.

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

Return a concise answer:

```text
Best next action: ...

Why: ...

ReasonTree path:
1. ...
2. ...
3. ...

Runner-up: ...

Key assumptions: ...

Failure check: ...
```

If evidence is weak, say so. If no branch is good enough, return the best partial path and the missing information needed to decide.

