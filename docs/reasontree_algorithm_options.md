# ReasonTree Algorithm Options

Research snapshot: 2026-07-02

This note turns the project idea into testable algorithm variants. The shared abstraction is:

```text
state -> action -> next_state -> score -> frontier selection
```

The goal is structured thinking, not classic MCTS visit-count theater. ReasonTree should help the user see possibilities level by level:

```text
S0: current situation
  A -> S1: likely consequence
  B -> S2: likely consequence
  C -> S3: likely consequence

Expand S1 and S2 because they scored highest or remain uncertain.
```

## Context Ledger

Before the tree starts, split the prompt into a context ledger:

```json
{
  "facts": ["observable or user-provided facts"],
  "assumptions_or_beliefs": ["premises that may be true but are not verified"],
  "user_preferences": ["risk tolerance, values, priorities, constraints"],
  "uncertainties": ["missing facts or unstable claims"],
  "hard_constraints": ["deadlines, budgets, rules, non-negotiables"]
}
```

This matters because many planning problems mix factual information with psychological beliefs or untested assumptions.

Example:

```text
Fact: The deadline is Friday.
Belief: If I ask for help, the team will think I am not capable.
Preference: I want a reversible move with low regret.
Uncertainty: I do not know whether the deadline can move.
```

ReasonTree should not flatten these into one context blob. Each branch should say which facts and assumptions it relies on.

## Baseline: Cached State-Action Beam

Best default for the repo.

```text
1. Frame current state S.
2. Propose 3 actions.
3. Simulate 3 next states.
4. Score siblings together on a 0-10 scale.
5. Keep top 1-2 branches.
6. Expand each selected node once.
7. Stop at depth 3 by default, depth 5 by explicit request.
8. Return both selected path and cross-tree synthesis.
```

Why this is strong:

- cheap enough for everyday use
- visually clear
- avoids repeated visits
- works for code, planning, research, data, writing, and personal decisions

What to measure:

- answer quality vs direct prompt
- latency
- number of model calls
- whether the final path is more actionable
- whether the runner-up and failure check are useful

## Option A: Batch Sibling Scorer

One scorer sees all children of a node.

Prompt shape:

```text
Current state:
S0

Candidate next states:
1. A -> S1
2. B -> S2
3. C -> S3

Score each 0-10 for:
- goal fit
- reversibility
- risk
- evidence strength
- learning value

Return a ranked table and the main reason for the ordering.
```

Use this for:

- product decisions
- project planning
- research synthesis
- personal decision practice
- writing strategy

Advantages:

- cheaper than independent scoring
- naturally calibrated because siblings are compared together
- easy to show in the UI

Failure mode:

- the scorer can share one blind spot across the whole level

## Option B: Independent Branch Scorers

Each branch is scored in isolation.

Use this for:

- code branches with separate test output
- long research branches
- branches with very different evidence packets

Advantages:

- parallelizable
- less anchoring from sibling options
- branch evidence can be longer

Failure mode:

- scores may drift because each scorer has a different local context

Mitigation:

- normalize scores after all independent results return
- ask one final comparative scorer to rank only the top candidates

## Option C: Hybrid Tournament

Recommended practical variant.

```text
1. Batch-score all siblings.
2. If score gap >= 2.0/10, expand the winner.
3. If score gap < 2.0/10, independently rescore top 2.
4. If still close, expand both one level.
5. If both fail, write failure note and retry once.
```

Why this is likely best:

- cheap on easy decisions
- more robust on close decisions
- supports parallelism only when useful
- easy to explain in the article

## Option D: Diversity-First Root, Evidence-First Later

Root level should intentionally explore different styles:

- conservative / reversible
- ambitious / high-upside
- information-gathering

After root, switch to evidence-first selection:

```text
root: maximize diversity
depth 2+: maximize score and evidence
final: critic checks selected path
```

This is useful because many one-shot model failures happen at the first framing step. If root options are redundant, deeper search only explores the same idea more verbosely.

## Option E: Reflection-After-Failure

Do not reflect at every node. Reflect only when the search gets stuck.

Failure note:

```json
{
  "failed_goal": "what the branch tried to achieve",
  "why_failed": "constraint, test, evidence, or logic issue",
  "learned_constraint": "new thing the next search must respect",
  "retry_hint": "how the next branch should differ",
  "avoid_next": "what not to repeat"
}
```

Then retry from the most relevant state using the note. This gives backtracking without asking the identical prompt again.

## Option F: Tree Synthesis, Not Only Best Leaf

The final answer should not only return the highest-scoring leaf. It should also read across the tree.

Useful synthesis fields:

```json
{
  "selected_path": "best path",
  "runner_up": "second-best first action",
  "facts_that_mattered": ["facts used by the selected path"],
  "assumptions_that_changed_the_ranking": ["assumptions that made one branch beat another"],
  "beliefs_tested": ["beliefs the tree pressured or would falsify"],
  "robust_recommendation": "what still holds even if one assumption is wrong",
  "conditional_recommendation": "what changes if a key assumption flips"
}
```

Example answer shape:

```text
Given the facts, action A is strongest. It depends on assumption X.
If X is false, action B becomes the runner-up. But because A is reversible
and creates information quickly, the first practical move is still A1.
```

This is the difference between "tree search picked a leaf" and "the tree improved the user's thinking."

## Exploration Without Visit Counts

Instead of MCTS visit counts, use a readable exploration score:

```text
exploration_need =
  uncertainty
+ sibling_score_closeness
+ missing_evidence
+ root_strategy_redundancy
- verifier_confidence
- budget_pressure
```

Policy:

```text
if exploration_need high:
    expand runner-up or diverse branch
else:
    expand best branch
```

This is easier to explain to users than "we visited this node 20 times."

## Suggested Experiment Matrix

Run the same tasks under four modes:

| Mode | Proposer | Scorer | Frontier | Best task type |
| --- | --- | --- | --- | --- |
| `beam_batch` | one call, 3 actions | one batch sibling score | top 1-2 | default planning |
| `beam_independent` | one call, 3 actions | parallel branch scorers | top 1-2 | long evidence branches |
| `hybrid_tournament` | one call, 3 actions | batch, then top-2 rescore if close | top 1-2 | robust default |
| `diversity_root` | role-diverse actions | batch sibling score | one diverse root branch retained | ambiguous decisions |

Metrics:

- quality judged by task-specific verifier or rubric
- cost and model calls
- latency
- clarity of trace
- usefulness of runner-up
- whether failure notes prevent repeated bad branches

## Literature Mapping

- Tree of Thoughts supports exploring multiple coherent reasoning paths and self-evaluating choices.
- RAP supports explicit state, action, next-state planning with a language-model world model.
- LATS supports tree search with external feedback and reflection after failed trajectories.
- MCTS-DPO and AlphaLLM-CPL show why sibling comparisons and saved rejected branches can become useful preference data.

ReasonTree's practical synthesis:

```text
Tree of Thoughts style branching
+ RAP state/action/next_state framing
+ LATS failure reflection
+ beam search defaults for cost control
+ cached sibling scoring for daily usability
```

## Sources

- Tree of Thoughts: https://arxiv.org/abs/2305.10601
- RAP / Reasoning via Planning: https://arxiv.org/abs/2305.14992
- LATS: https://arxiv.org/abs/2310.04406
- MCTS-DPO: https://arxiv.org/abs/2405.00451
- AlphaLLM-CPL: https://arxiv.org/html/2410.06508v1
