---
description: Use ReasonTree search-time reasoning when a one-shot answer is brittle. Applies to chess, code repair, project decisions, finance/risk scenarios, research synthesis, learning, writing, and planning tasks with candidate actions and evaluable outcomes.
---

# ReasonTree

ReasonTree turns a brittle prompt into a bounded state-action search tree.

The goal is not to "think longer" or ask the same question repeatedly. The goal is to name the current state, branch into a few plausible actions, predict next states, score sibling branches against evidence or constraints, expand only the strongest paths, and return an auditable answer.

## Router

Do not blindly run tree search for every request.

Use a normal answer when:

- the task is simple
- there is one obvious answer
- no meaningful branch comparison exists
- search would add fake rigor

Ask 1-3 clarifying questions when a high-stakes task is underspecified. Prefer asking for:

- success criterion
- hard constraints
- risk tolerance
- deadline
- available verifier

Run ReasonTree when:

- 2-5 plausible choices exist
- wrong commitment is costly
- branch outcomes can be scored
- the user asks for a decision, plan, repair, diagnosis, or synthesis

Use verifier-backed ReasonTree when a checker exists:

- tests, build, type check, linter, benchmark
- SQL reconciliation or data-quality checks
- schema or policy validation
- source citations
- legal/policy checklist
- chess/legal-line/mate verifier
- calculator, spreadsheet, theorem prover, or code-quality checks

Default budget:

- `max_depth`: 3
- `branch_width`: 3
- `beam_width`: 2
- `max_nodes`: 48

Maximum recommended budget:

- `max_depth`: 5
- `branch_width`: 5 only for shallow searches
- Always cap total nodes before expanding.

## Search Contract

1. Define the initial state, goal, constraints, and success criteria.
2. Build a context ledger: facts, assumptions/beliefs, user preferences, uncertainties, and constraints.
3. Identify the best available verifier or scoring rubric.
4. Generate 3 candidate actions for the current state. Use up to 5 only when the task clearly needs wider exploration.
5. Simulate or inspect each action into a next state.
6. Attach node notes: facts used, assumptions used, beliefs tested, and broader implication.
7. Score sibling next states together on a 0-10 scale when the task is subjective or planning-oriented.
8. Cache expansions by task/state/depth so the same state is not re-asked from scratch.
9. Keep the best 1-2 branches plus one diverse branch when uncertainty is high.
10. Expand each selected node once by default.
11. Stop early when a hard verifier passes a terminal solution.
12. If all branches fail, write a failure note and use it to guide one retry instead of restarting blindly.
13. Verify the selected path with a critic pass.
14. Return the best path, runner-up, tree synthesis, score details, and failure check.

This is MCTS-inspired, not naive classic MCTS. Do not repeatedly revisit the same prompt just to increase visit counts.

Revisit a state only when:

- a verifier produced a near miss and suggests a targeted repair
- a failure note changes the next expansion
- top branches are close and uncertainty is high
- a hard constraint was discovered late
- a different role is inspecting the same state, such as critic or repairer

## Scoring

Prefer hard verifiers. If no hard verifier exists, use an explicit score vector:

```json
{
  "correctness": 0.0,
  "constraint_fit": 0.0,
  "risk": 0.0,
  "cost": 0.0,
  "reversibility": 0.0,
  "evidence_strength": 0.0,
  "novelty": 0.0
}
```

For hard-verifier tasks, a failed verifier dominates fluent explanation. Do not mark a branch successful when tests, schemas, legality checks, or source evidence fail.

Exploration means diverse strategies, evidence lenses, or hypotheses. Exploitation means expanding the branch with the strongest verified progress. It does not mean asking the identical prompt many times.

## Verification

When the task has a reliable verifier, use it as the scorer instead of relying on narrative confidence. Examples:

- Chess: compare the final answer against a withheld answer key or legal-line/mate check after the workflow has produced its line.
- Code repair: run the relevant tests against each candidate patch when possible.
- Data/SQL: reconcile row counts, totals, sample sizes, and metric definitions.
- Planning or finance/risk: verify against stated constraints, risk limits, deadlines, and reversibility.

If no external verifier exists, do a critic pass and state the weakest assumption in the selected path.

## Failure Notes

When no path succeeds, do not restart from scratch. Write a compact note and use it as state for one retry if budget remains:

```json
{
  "failed_goal": "what was attempted",
  "why_failed": "verifier result or violated constraint",
  "useful_evidence": ["facts learned"],
  "retry_hint": "how the next branch should differ"
}
```

If the retry also fails, return the best partial path, the missing evidence, and the exact constraint that prevents a stronger answer.

## Parallelization

Use parallel work only where branches are independent.

Good parallel work:

- run local verifiers for candidate branches
- inspect independent code paths
- test independent patches in separate sandboxes
- compare separate hypotheses or data slices

Avoid:

- unbounded recursive subagents
- asking multiple agents the identical prompt without a scorer
- using parallelism when the user only needs a direct answer

For most user tasks, use one proposer call that returns 3 branches, then parallelize verification when tools are available.

## State-Action Format

Use this mental model internally:

```json
{
  "state": "what is currently true",
  "action": "what we could do next",
  "next_state": "what likely becomes true after the action",
  "score": 7.5,
  "score_reason": "why this branch is ranked here",
  "facts_used": ["factual inputs this branch depends on"],
  "assumptions_used": ["beliefs, preferences, or psychological premises this branch assumes"],
  "beliefs_tested": ["assumptions this branch pressures or would falsify"],
  "node_notes": ["what this node teaches the larger tree"],
  "uncertainty": 0.3,
  "failure_modes": ["what could make this branch fail"]
}
```

For general planning, score sibling branches in one comparative pass:

```text
Given state S0 and next states S1, S2, S3, score each 0-10 for goal fit,
risk, reversibility, evidence strength, and learning value.
```

Independently rescore the top branch and runner-up only when the score gap is small or the decision is high impact.

## Context Ledger

Before expanding the tree, separate inputs into:

```json
{
  "facts": ["observable or user-provided facts"],
  "assumptions_or_beliefs": ["premises that may be true but are not verified"],
  "user_preferences": ["risk tolerance, values, priorities, constraints"],
  "uncertainties": ["missing facts or unstable claims"],
  "hard_constraints": ["deadlines, budgets, rules, non-negotiables"]
}
```

Treat psychological beliefs as assumptions, not facts. Example:

```text
Fact: I have 10 days before the deadline.
Belief: If I ask for help, people will think I am weak.
Preference: I want the lowest-regret reversible move.
Uncertainty: I do not know whether the reviewer is flexible.
```

Branches should test or route around these assumptions where possible. The final answer should not simply say "best branch wins." It should synthesize across the tree:

```text
Given the facts, path A scores highest. Even if assumption X is true, path A remains reversible.
If assumption X is false, path B becomes nearly as good. The practical next move is therefore ...
```

## Repo-Local Fast Path

When this skill is used inside the ReasonTree repo and the task is a chess FEN with `mate in N`, use the local verifier as the scorer:

```bash
.venv/bin/python scripts/chess_mate_search.py --fen "<FEN>" --mate-in <N>
```

Use the verifier to check the final line, then return the first solution as the selected ReasonTree path. Do not spend extra turns analyzing the board after the verifier returns a forced mate.

## Output Contract

```json
{
  "best_action": "first action to take",
  "confidence": 0.0,
  "path": [
    {
      "depth": 1,
      "action": "candidate action",
      "state": "resulting state",
      "score": 0.0,
      "rationale": "short reason"
    }
  ],
  "runner_up": "second best first action",
  "tree_synthesis": {
    "facts_that_mattered": [],
    "assumptions_that_changed_the_ranking": [],
    "beliefs_tested": [],
    "cross_tree_notes": []
  },
  "score_detail": {
    "verifier_status": "pass|fail|partial|not_applicable",
    "evidence_strength": 0.0,
    "risk": 0.0
  },
  "failure_notes": [],
  "failure_check": "what could make this answer wrong"
}
```

## Use Cases

- Chess or tactical puzzles with known labels.
- Code repair where candidate patches can be tested.
- Project-management choices with deadline, risk, and reversibility constraints.
- Finance or strategy scenarios framed as risk planning, not investment advice.
- Research synthesis where branches represent competing hypotheses.
- Learning, writing, and personal decision practice where the goal is structured reflection.

## Guardrails

- Do not expand more than 5 levels.
- Do not generate more than 5 actions per level.
- Prefer 3 actions and 3 levels unless the user explicitly asks for deeper search.
- Do not mark success unless all hard constraints are satisfied.
- If the scorer is weak or ungrounded, say so.
