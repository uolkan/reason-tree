# ReasonTree Use Cases

Research snapshot: 2026-07-02

ReasonTree is not meant for every Claude prompt. It is useful when the task has:

- multiple plausible paths
- meaningful tradeoffs
- a way to score or verify branches
- risk from committing too early to the first answer
- enough value to justify extra model/tool calls

It is usually not useful for simple recall, rewriting, summarization with no decision, or tasks where the user already knows the exact desired output.

## Positioning

ReasonTree should be described as:

> A cached, shallow, parallelizable state-action tree for hard Claude tasks where one-shot answers are brittle.

It should not be described as:

> A universal intelligence booster.

The stronger claim is:

> ReasonTree helps when a problem can be decomposed into states, candidate actions, next states, and branch scores before final selection.

Chess is the visual demo. The product is structured thinking: "if we do this, this state follows; if we do that, that state follows."

## Claude User Context

Anthropic's public pages and customer stories point to recurring production use cases:

- Enterprises and startups use Claude across financial services, healthcare, legal, government, education, and software.
- Claude agents are positioned for customer support, coding, and tool-using workflows.
- Claude Enterprise emphasizes governance, data controls, auditability, regulated industries, and organization-wide deployment.
- Claude Code is positioned for writing, testing, debugging, codebase analysis, and command-running workflows.
- Legal and finance customer stories emphasize source attribution, verifiability, citations, compliance, and decision-grade outputs.

ReasonTree fits best where the user needs more than fluent text: they need a structured decision path that can be audited.

## Ranked Use Cases

### 1. Code Repair And Refactoring

Why it fits:

- Multiple fixes may be plausible.
- Tests, type checks, linters, benchmarks, and diff review provide real verifiers.
- Branches can be explored independently.

ReasonTree shape:

1. Define the current state: failing behavior, constraints, and success test.
2. Generate 3 candidate actions: minimal patch, safer refactor, diagnostic-first path.
3. Simulate the next state for each action.
4. Score by tests passed, blast radius, simplicity, and maintainability.
5. Keep the best patch path and explain rejected alternatives.

Verifier examples:

- unit tests
- integration tests
- static type checks
- lint
- build
- benchmark threshold
- small reproduction script

Best default:

- depth 3
- branch width 3
- beam width 1-2
- no repeated visits unless patch attempts are stochastic or test evidence conflicts

### 2. Data Analysis And Business Diagnostics

Why it fits:

- Metric changes usually have several possible explanations.
- SQL checks can verify or reject hypotheses.
- Stakeholders need a defensible causal story, not just a chart.

ReasonTree shape:

1. Current state: metric moved, definition, time window, known events.
2. Candidate actions: segment check, data-quality check, causal hypothesis check.
3. Next states: what each query or diagnostic would reveal.
4. Score by explanatory power, sample size, consistency, and confound risk.
5. Return primary driver, runner-up, and caveats.

Verifier examples:

- SQL query result
- reconciliation to source totals
- segment decomposition
- holdout/control comparison
- data-quality checks
- metric definition audit

### 3. Product, Project, And Strategy Decisions

Why it fits:

- Real decisions involve competing options, constraints, risks, and reversibility.
- The output should be a decision memo with assumptions and failure modes.
- Verification is weaker than code/tests but still possible through constraints and evidence.

ReasonTree shape:

1. Current state: goal, available options, hard constraints, deadline.
2. Candidate actions: ship now, delay, scope cut, experiment first, rollback plan.
3. Next states: expected business/user/engineering state after each action.
4. Score by expected value, reversibility, time-to-learn, risk, and opportunity cost.
5. Expand the top 1-2 options into implementation paths.

Verifier examples:

- deadline fit
- budget fit
- dependency map
- stakeholder constraints
- reversibility check
- known data or customer evidence

Best default:

- branch width 3
- depth 2-3
- one reflection pass if all options are weak

### 4. Research Synthesis And Literature Review

Why it fits:

- Research questions often have competing hypotheses.
- Sources can support or contradict branches.
- A tree helps preserve uncertainty and prevent premature synthesis.

ReasonTree shape:

1. Current state: research question, scope, known sources.
2. Candidate actions: thesis A, thesis B, thesis C, or "missing evidence first."
3. Next states: what would be true if that thesis is pursued.
4. Score by source quality, recency, agreement, and methodological strength.
5. Return synthesis, counterarguments, and open questions.

Verifier examples:

- primary sources
- paper metadata
- direct claims mapped to citations
- replication status
- benchmark caveats

### 5. Learning, Writing, And Personal Decision Practice

Why it fits:

- Many users want to think through a decision, essay, career move, study plan, or negotiation.
- The value is not a hard verifier; it is structured reflection.
- State-action-next-state trees help users see consequences before committing.

ReasonTree shape:

1. Current state: user goal, situation, constraints, emotional or practical priorities.
2. Candidate actions: conservative, ambitious, information-gathering.
3. Next states: likely benefits, costs, second-order effects.
4. Score by goal fit, reversibility, regret risk, and learning value.
5. Return a recommended next action plus a runner-up.

Verifier examples:

- stated personal constraints
- deadline and cost fit
- consistency with user priorities
- reversibility
- concrete next-step clarity

### 6. Legal And Compliance Workflow Support

Why it fits:

- Legal/compliance workflows need source-grounded conclusions.
- Branches map to interpretations, clauses, or risk positions.
- Exact quote/citation behavior is a strong verifier pattern.

ReasonTree shape:

1. Identify the workflow question and controlling sources.
2. Generate candidate interpretations or risk flags.
3. For each, require supporting source text.
4. Score by citation quality, policy fit, jurisdiction/scope match, and confidence.
5. Return the answer with caveats and escalation triggers.

Verifier examples:

- exact quoted source text
- statute/regulation citation
- contract clause reference
- company playbook
- jurisdiction match
- counsel review required flag

Guardrail:

- The output should be workflow support, not legal advice.

### 7. Customer Support Agent Debugging

Why it fits:

- AI support failures often involve edge cases, incorrect policies, or bad tool routing.
- Conversation tests can verify fixes.
- Anthropic customer stories already highlight regression testing for support agents.

ReasonTree shape:

1. Classify failure mode.
2. Generate candidate fixes: prompt, tool, policy, routing, retrieval, escalation.
3. Run regression conversations.
4. Score by pass rate, policy compliance, customer tone, and escalation correctness.
5. Return fix plus regression evidence.

Verifier examples:

- golden conversation suite
- policy classifier
- escalation rule check
- retrieval source check
- human review labels

### 8. Finance, Risk, And Due Diligence

Why it fits:

- Finance workflows need traceable numbers and assumptions.
- Scenarios are naturally branch-like.
- Outputs must be auditable and source-attributed.

ReasonTree shape:

1. Define decision or risk question.
2. Generate scenarios or diligence hypotheses.
3. Score by source quality, financial impact, probability, and downside risk.
4. Stress test top branches.
5. Return recommendation, sensitivities, and decision triggers.

Verifier examples:

- spreadsheet formulas
- source-attributed numbers
- reconciliation checks
- covenant or compliance constraints
- scenario sensitivity table

Guardrail:

- Keep as analysis/risk planning, not investment advice.

## State-Action Framing

Start by separating context:

```json
{
  "facts": ["what is known"],
  "assumptions_or_beliefs": ["what may be true but is not verified"],
  "user_preferences": ["what the user values"],
  "uncertainties": ["what is missing"],
  "hard_constraints": ["what cannot be violated"]
}
```

This lets ReasonTree handle factual information and belief-like premises differently. A belief may still be important, especially in personal decisions, but it should not be treated as a verified fact.

Every ReasonTree node should be compact:

```json
{
  "state": "what is currently true",
  "available_actions": ["A", "B", "C"],
  "chosen_action": "A",
  "next_state": "what becomes true after A",
  "score": 7.8,
  "score_reason": "why this next state is promising",
  "facts_used": ["facts this node depends on"],
  "assumptions_used": ["beliefs or premises this node depends on"],
  "beliefs_tested": ["assumptions this node pressures"],
  "node_notes": ["what this node teaches the broader tree"],
  "uncertainty": 0.3,
  "failure_modes": ["what could make this branch bad"]
}
```

This makes the workflow feel like a mental planning practice:

```text
State S0
  Action A -> State S1 -> Action A1 -> State S1a
  Action B -> State S2 -> Action B1 -> State S2a
  Action C -> State S3 -> Action C1 -> State S3a
```

The LLM's best role is not only answering. It should:

- name the current state
- propose diverse actions
- predict plausible next states
- compare sibling branches
- identify uncertainty and missing evidence
- produce a concise failure note when a branch collapses
- synthesize across the whole tree before giving the final answer

The final answer should include both the selected path and the cross-tree lesson:

```text
Given the facts, action A is strongest. It depends on assumption X.
If X is wrong, action B becomes more attractive. But because A is reversible
and creates information quickly, the recommended first move is still A1.
```

## Level-Wise Scoring

There are two useful scoring modes.

### Batch Sibling Scoring

Score all sibling branches in one call:

```text
Given the current state and these 3 next states, score each 0-10 for goal fit,
risk, reversibility, and evidence strength. Explain the ranking.
```

Advantages:

- cheaper than one scorer call per branch
- encourages relative judgment
- good for planning, writing, research, business decisions

Risk:

- one scorer can share the same blind spot across all branches

### Independent Branch Scoring

Score each branch independently:

```text
Given this state-action-next_state branch, score it 0-10 and list failure modes.
```

Advantages:

- less anchoring from seeing sibling branches
- easier to parallelize
- better when branch evidence is long

Risk:

- scores can drift because branches are not calibrated against each other

Recommended default:

- use batch sibling scoring at each level
- independently re-score only the top branch and the runner-up when the score gap is small

## Exploration vs Exploitation

ReasonTree does not need classic repeated MCTS visits by default.

Use exploration when:

- there are many plausible options
- the first answer is likely biased
- missing a path is expensive
- the scorer is uncertain
- no branch has a clear lead

Use exploitation when:

- a branch passes a hard verifier
- a terminal solution is found
- score gap is large
- additional search has low expected value
- budget or time is constrained

Practical policy:

```text
if hard verifier passes terminal branch:
    stop
elif all top branches fail:
    reflect, write failure note, generate revised candidates
elif top branch score - runner up score >= threshold:
    exploit top branch
else:
    expand top 2 branches one more level
```

Suggested thresholds:

- hard verifier pass: stop
- score gap >= 2.0 on a 0-10 scale: exploit
- score gap < 2.0: expand runner-up too
- all scores < 4.0: reflection pass
- depth >= 5: stop and report uncertainty

## Failure Notes And Reflection

When no path succeeds, ReasonTree should not just return "failed." It should write a compact note:

```json
{
  "failed_goal": "what we tried to solve",
  "failed_branches": [
    {"action": "A", "reason": "failed test X"},
    {"action": "B", "reason": "violated constraint Y"}
  ],
  "new_constraints": ["what we learned"],
  "next_candidates": ["what to try next"],
  "user_question": "only if needed"
}
```

The next search round should use this note as state, not restart from scratch.

This is where ReasonTree differs from naive tree search: failed branches become structured context for the next attempt.

## Parallelization

Parallelize only independent work:

- branch scoring
- local verifiers
- code tests in isolated worktrees
- source retrieval per research hypothesis
- separate critic checks by role

Avoid parallelizing unbounded model calls by default. Claude subscription/API cost can multiply quickly.

Recommended default:

- one proposer call returns 3 branches
- one batch scorer ranks siblings per level
- optionally parallelize independent evidence checks
- independently re-score top 2 only when the ranking is close

## Use-Case Fit Table

| Use case | Fit | Best verifier/scorer | Exploration need | Notes |
| --- | --- | --- | --- | --- |
| Code repair | Very high | tests/build/typecheck | medium | Best practical demo after chess |
| Data diagnostics | Very high | SQL/data checks | medium | Strong business use case |
| Product/project decision | High | constraints/risk matrix | medium | Avoid analysis paralysis |
| Research synthesis | Medium-high | primary sources | high | Needs source discipline |
| Personal decision practice | Medium-high | user constraints/rubric | medium | Strong general Claude use case |
| Legal/compliance workflow support | High | citations/exact quotes | medium | Workflow support, not advice |
| Customer support debugging | High | regression conversations | medium | Strong Claude-agent customer fit |
| Finance/risk | Medium-high | source-attributed numbers | medium | Analysis, not advice |
| Simple writing | Low | user preference | low | Normal Claude is enough |
| Basic Q&A | Low | direct answer | low | ReasonTree overkill |

## Sources

- Anthropic customer stories: https://claude.com/customers
- Claude agents solution page: https://claude.com/solutions/agents
- Claude Enterprise: https://www.anthropic.com/product/enterprise
- Claude coding solution page: https://claude.com/solutions/coding
- Claude customer support solution page: https://claude.com/solutions/customer-support
- Claude financial services solution page: https://claude.com/solutions/financial-services
- Claude government solution page: https://claude.com/solutions/government
- Claude education solution page: https://claude.com/solutions/education
- GC AI legal customer story: https://claude.com/customers/gc-ai
- Claude Platform use-case guides: https://platform.claude.com/docs/en/about-claude/use-case-guides/overview
