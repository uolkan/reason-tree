# ReasonTree Design Brainstorm

Research snapshot: 2026-07-02

This file consolidates local design discussion, four parallel sub-agent brainstorms, the LLM MCTS literature notes, and current Claude/Anthropic documentation. The practical conclusion is clear:

> ReasonTree should be a state-action problem-framing router and cached tree-search workflow, not a naive MCTS loop that repeatedly revisits the same node.

## Design Thesis

ReasonTree should help Claude users when a task is too brittle for a one-shot answer but structured enough to represent as states, actions, next states, and branch scores.

The right default is:

```text
frame state -> propose diverse actions -> simulate next states -> score siblings -> keep small beam -> expand -> critic -> answer
```

Not:

```text
ask the same model the same prompt 20 times
```

The algorithm is MCTS-inspired, but the product should be described as:

> Cached state-action beam tree search.

Or shorter:

> Structured state-action reasoning for Claude.

## Why Not Classic MCTS By Default

Classic MCTS works well when rollouts are cheap and stochastic. A Go engine can run thousands of simulations and use visit counts to estimate value.

LLM calls are different:

- each model call costs time and money
- repeated identical prompts are not independent rollouts in the same sense
- value estimates are often noisy unless grounded by a verifier
- context grows quickly
- user workflows need bounded latency

Therefore, ReasonTree should expand each selected node once by default, cache the result, and revisit only when new information changes the state.

Revisit only when:

- a verifier produced a near miss and suggests targeted repair
- a reflection note exists after failure
- top branches are close and uncertainty is high
- a hard constraint was discovered late
- the same state is being inspected by a different role, such as critic or repairer

## Router First

When the user invokes `/reasontree`, the skill should not blindly run tree search. It should first classify the request.

### Route 1: Normal Answer

Use when:

- question is simple
- there is one obvious answer
- search would add fake seriousness
- no meaningful branch comparison exists

Example:

```text
/reasontree rewrite this sentence more clearly
```

Response should be a normal concise answer, possibly noting that tree search is unnecessary.

### Route 2: Ask Clarifying Question

Use when high-stakes search would be under-specified.

Ask at most 1-3 questions. Typical missing fields:

- success criterion
- hard constraints
- risk tolerance
- deadline
- available verifier
- decision owner

Example:

```text
Before running ReasonTree, I need the success metric and the hard deadline.
```

### Route 3: Run Tree Search

Use when:

- 2-5 plausible choices exist
- wrong commitment is costly
- branch outcomes can be scored
- user asks for a decision, plan, repair, diagnosis, or synthesis

### Route 4: Verifier-Backed Search

Use when a hard or semi-hard checker exists:

- tests
- schema validation
- SQL reconciliation
- source citations
- policy checklist
- chess/legal-line checker
- theorem prover
- calculator/spreadsheet
- static analysis

This is the best mode.

### Route 5: Soft Scoring With Caveat

Use when no hard verifier exists but branch comparison still helps:

- product decision
- project planning
- strategy
- finance/risk scenario planning
- research hypothesis ranking

Output must say scoring is rubric-based, not verified.

## Default Algorithm

```text
frame_task(task):
  identify goal, constraints, verifier, scorer, stop condition
  if missing critical information:
    ask one concise clarifying question

root = Node(framed_problem)
frontier = [root]
notes = []

for depth in 1..max_depth:
  selected = choose frontier by score, uncertainty, diversity, and budget

  for each selected node:
    branches = cached expansion if available
    otherwise proposer returns 3 candidate actions

    for each branch, preferably in parallel:
      simulate next state if needed
      run verifier/scorer
      compute score vector
      mark terminal if solved or failed

  if hard verifier passes a terminal branch:
    return verified path

  if all branches fail:
    reflection_note = summarize failure and retry hints
    if retry budget remains:
      continue with reflection note
    else:
      return best partial answer plus missing evidence

  frontier = top beam branches plus one diversity branch if useful

critic(selected_path)
return recommendation, trace, runner-up, failure check
```

## Defaults

```text
max_depth: 3
branch_width: 3
beam_width: 2
max_nodes: 24-48
max_depth_cap: 5
branch_width_cap: 5
reflection_rounds: 1 default, 2 max
revisit_same_node: false by default
parallel_verification: true
parallel_model_proposers: opt-in
```

## State-Action-Next-State Contract

ReasonTree should feel like a mental planning practice, not a hidden prompt trick.

Before expansion, create a context ledger:

```json
{
  "facts": ["observable or user-provided facts"],
  "assumptions_or_beliefs": ["untested premises, including psychological beliefs"],
  "user_preferences": ["risk tolerance, values, priorities"],
  "uncertainties": ["missing or unstable information"],
  "hard_constraints": ["deadlines, budgets, rules"]
}
```

The tree should treat facts and beliefs differently. A belief can shape branch scoring, but it should be marked as an assumption and, where possible, tested or routed around.

Every node should be expressible as:

```json
{
  "state": "what is currently true",
  "action": "what we could do next",
  "next_state": "what likely becomes true after the action",
  "score": 7.4,
  "score_reason": "why this next state is better or worse",
  "facts_used": ["facts this branch relies on"],
  "assumptions_used": ["beliefs, preferences, or premises this branch relies on"],
  "beliefs_tested": ["assumptions this branch would test"],
  "node_notes": ["what this node teaches the larger tree"],
  "uncertainty": 0.3,
  "failure_modes": ["what could make this branch fail"]
}
```

For most non-code tasks, the LLM should first name the state and action space:

```text
S0: current situation
Actions: A, B, C
A -> S1
B -> S2
C -> S3
```

Then it should expand only the best next states:

```text
S1 -> A1, A2, A3
S2 -> B1, B2, B3
```

This keeps the tree legible. The goal is not to produce a long chain of thought. The goal is to make options and consequences visible.

## Tree Synthesis

The final answer should not only return the best leaf. It should synthesize across the tree:

```json
{
  "best_path": "selected path",
  "runner_up": "second-best first action",
  "facts_that_mattered": ["facts that consistently affected scoring"],
  "assumptions_that_changed_the_ranking": ["beliefs or premises that changed branch order"],
  "beliefs_tested": ["beliefs the tree pressures or would falsify"],
  "robust_recommendation": "what remains true across branches",
  "conditional_recommendation": "what changes if a key assumption flips"
}
```

Example:

```text
Given the facts, A is strongest. It assumes X. If X is false, B becomes close.
But A is reversible and produces information quickly, so the first move is A1.
```

This is the main product difference between ReasonTree and a normal beam search trace.

## Level-Wise Comparative Scoring

There are three scoring strategies worth testing.

### Strategy A: Batch Sibling Scoring

Score all children of the same parent in one scorer call.

```text
Given state S0 and candidate next states S1, S2, S3,
score each 0-10 for goal fit, reversibility, risk, evidence strength, and learning value.
Return a ranked table.
```

This is probably the best default for general planning because it makes the model calibrate branches against each other.

Pros:

- cheap
- naturally comparative
- good for business, personal decisions, research, writing, planning

Cons:

- one scorer can share the same blind spot across all siblings
- long branches can crowd the prompt

### Strategy B: Independent Branch Scoring

Give each branch to a separate scorer.

Pros:

- easy to parallelize
- less sibling anchoring
- useful when each branch has long evidence

Cons:

- scores may not be calibrated
- more model calls
- can feel heavier than needed for everyday use

### Strategy C: Hybrid Tournament

Use one batch scorer at every level, then independently rescore the top branch and runner-up only when:

- score gap is small
- top branch has high uncertainty
- the decision is high impact
- hard constraints are close to being violated

This is the recommended default to test first.

## Scoring Model

Do not rely on one vague model-confidence number. Store a score vector, preferably on a 0-10 scale for user-facing traces.

```json
{
  "branch_id": "d2_b1",
  "action": "candidate action",
  "state_delta": "what changed",
  "verifier": {
    "type": "unit_tests|hard|retrieval|rubric|judge|critic",
    "status": "pass|fail|partial|not_applicable",
    "evidence": ["short evidence refs"]
  },
  "scores": {
    "correctness": 0.0,
    "constraint_fit": 0.0,
    "risk": 0.0,
    "cost": 0.0,
    "reversibility": 0.0,
    "evidence_strength": 0.0,
    "novelty": 0.0
  },
  "aggregate": 0.0,
  "confidence": 0.0,
  "failure_modes": ["what could break this branch"]
}
```

Simple aggregate:

```text
aggregate =
  0.45 * verifier_result
+ 0.20 * constraint_fit
+ 0.15 * evidence_strength
+ 0.10 * progress_to_goal
+ 0.10 * robustness
- 0.10 * cost_or_risk_penalty
```

Override rule:

> If a hard verifier fails, a fluent explanation cannot rescue the branch.

## Exploration vs Exploitation

ReasonTree still needs exploration, but not repeated visits.

Exploration means:

- different strategies
- different decomposition
- different verifier lens
- different risk posture
- different evidence source
- different critic role

Exploitation means:

- expand the branch with the strongest verified progress
- stop early on hard verifier success
- spend critic effort on the selected path

Selection score:

```text
selection_score =
  Q
+ exploration_c * uncertainty
+ diversity_c * novelty
- cost_c * estimated_cost
- risk_c * irreversible_risk
```

Suggested `exploration_c`:

- code with hard tests: `0.10-0.20`
- business/project decisions: `0.30-0.45`
- research synthesis: `0.35-0.50`
- finance/risk planning: `0.25-0.40`
- personal decision practice: `0.25-0.45`

Keep one diverse branch at root unless a hard verifier already found the answer.

Alternative non-visit exploration signal:

```text
exploration_need =
  uncertainty
+ sibling_score_closeness
+ strategy_redundancy_penalty
+ missing_evidence
- verifier_confidence
- budget_pressure
```

If `exploration_need` is high, expand the runner-up or a diverse branch. If it is low, exploit the best branch. This replaces repeated visit counts with a more human-readable reason for whether the tree is sufficiently explored.

## Failure Notes

When no branch succeeds, ReasonTree should not restart from scratch. It should produce a failure note and use it as state for one retry.

```json
{
  "failed_goal": "what we tried to solve",
  "failed_paths": [
    {
      "action": "candidate A",
      "reason": "failed test X",
      "lesson": "the selected action depends on an untested stakeholder assumption",
      "avoid_next": "do not repeat a full-launch branch unless new evidence changes the risk"
    }
  ],
  "learned_constraints": ["rollback must be under 1 hour"],
  "missing_info": ["success metric not defined"],
  "retry_frame": "generate only reversible options that satisfy budget and rollback",
  "user_question": "only if needed"
}
```

This is the practical version of reflection/memory from LATS-style systems:

- reflection after terminal failure
- not reflection at every node
- failed branches become structured context
- retry is targeted, not repetitive

## Parallelization

Claude Code and Agent SDK documentation position subagents as useful for context isolation, parallel independent work, specialized instructions, and tool restrictions. ReasonTree should use subagents for those purposes, not as a default way to ask the same question many times.

Good parallelism:

- run branch verifiers independently
- run tests for candidate patches in isolated worktrees
- retrieve sources for different research hypotheses
- run separate critic roles after a selected path exists
- compare policy/risk interpretations in regulated workflows

Bad parallelism:

- spawn five agents to answer the exact same prompt
- let every branch recursively spawn unbounded agents
- use subagents without a scorer
- parallelize high-cost model calls before local checks

Recommended pattern:

```text
one proposer call -> 3 branches
parallel local verification -> scores
beam select -> expand top 1-2
critic only on selected path
reflect only after failure
```

## Sub-Agent Roles

### Proposer

Generates 3 diverse candidate actions.

Prompt posture examples:

- safe/minimal
- aggressive/high-upside
- information-gathering
- skeptical or risk-first

### Verifier Workers

Run checks that can be isolated:

- tests
- SQL
- source retrieval
- policy checklist
- chess verifier

### Critic

Runs only after a candidate path is selected. Its job is to find why the path could be wrong.

### Reflector

Runs only after failure. Produces failure notes and retry frame.

## Output Contract

Reader-facing output should be short first, trace second.

```text
Recommendation: ...
Confidence: medium
Verifier: pytest passed / source-supported / constraints-only
First action: ...
Why: ...
Runner-up: ...
Failure check: ...
```

Trace:

```text
Depth 1: option A, score 0.72
Depth 2: narrower A1, score 0.81
Depth 3: verified path, score 0.90
```

If not verified:

```text
No verified path found.
Best partial path: ...
Why it is incomplete: ...
Needed evidence: ...
Recommended next step: ...
```

## Product Names For The Internal Algorithm

Do not overbrand this in the README, but internally we can use one of:

- CVBT: Cached Verifier-Guided Beam Tree
- VBT: Verifier-Guided Beam Tree
- CFS: Cached Frontier Search
- VFT: Verified Frontier Tree

Best internal name:

> Cached Verifier-Guided Beam Tree

It is more accurate than "MCTS" for the default ReasonTree behavior.

## Source Notes

- Claude Code skills are reusable instruction folders invoked directly as `/skill-name`; their body loads only when used, which fits ReasonTree as a skill.
- Claude Code subagents isolate context, run parallel subtasks, apply specialized instructions, and can restrict tools.
- Claude Code commands include workflows that fan work out across many subagents, but ReasonTree should keep fan-out bounded.
- Anthropic customer and solution pages show strong demand across coding, customer support, legal, finance, government, education/research, and enterprise workflows.

Sources:

- Claude skills docs: https://code.claude.com/docs/en/skills
- Claude Code CLI docs: https://code.claude.com/docs/en/cli-reference
- Claude Code subagents docs: https://code.claude.com/docs/en/agent-sdk/subagents
- Claude commands docs: https://code.claude.com/docs/en/commands
- Anthropic customers: https://claude.com/customers
- Claude Enterprise: https://www.anthropic.com/product/enterprise
- Claude agents: https://claude.com/solutions/agents
- Claude coding: https://claude.com/solutions/coding
- Claude customer support: https://claude.com/solutions/customer-support
- Claude financial services: https://claude.com/solutions/financial-services
