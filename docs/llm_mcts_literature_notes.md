# LLM MCTS Literature Notes

Research snapshot: 2026-07-02

These notes summarize recent work on using Monte Carlo Tree Search, tree search, and related search-time reasoning methods with large language models. The goal is not to copy any paper exactly. The goal is to shape ReasonTree into a practical state-action reasoning workflow for Claude Code users.

## Short Verdict

There is a real research line here. The strongest recurring pattern is:

1. Use the LLM as a policy or proposer.
2. Represent partial reasoning as explicit states and actions.
3. Search over multiple candidate trajectories instead of trusting one chain.
4. Use a value model, process reward model, external environment, code execution, theorem prover, or task verifier as the scorer.
5. Backpropagate or rank branch values.
6. Optionally distill high-value trajectories back into the model.

For ReasonTree, the important engineering lesson is that classic MCTS should be adapted for expensive LLM calls. We should not repeatedly revisit the same node by default. Use bounded beam or best-first expansion, cache every node, parallelize independent branches, and prefer external verifiers over LLM self-judgment.

For general user-facing tasks, the most important abstraction is:

```text
state -> action -> next_state -> score -> select frontier
```

This turns reasoning into a structured planning practice instead of a longer hidden monologue.

## Core Papers And What They Teach

### RAP - Reasoning via Planning

Source: [Reasoning with Language Model is Planning with World Model](https://arxiv.org/abs/2305.14992), EMNLP 2023.

RAP frames reasoning as planning. The LLM plays two roles:

- agent or policy: proposes reasoning actions
- world model: predicts the next state after an action

It then uses MCTS and task-specific rewards to balance exploration and exploitation across reasoning paths. This is directly relevant to ReasonTree's proposer/simulator/scorer split. The key idea is not "ask the model to think longer." It is "make the state transition explicit, then search."

ReasonTree implication:

- Keep `state`, `action`, `next_state`, `score`, and `terminal` as first-class fields.
- Treat Claude as proposer and simulator, not as the only judge.
- Use task-specific rewards whenever possible.

### Tree of Thoughts

Source: [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601), 2023.

Tree of Thoughts is not MCTS, but it is the closest practical ancestor for user-facing reasoning workflows. It generalizes chain-of-thought into a tree of coherent intermediate thoughts and uses BFS/DFS plus LM self-evaluation. The paper reports large gains on tasks that need search and backtracking, such as Game of 24.

ReasonTree implication:

- For expensive models, BFS/beam search can be more practical than full MCTS.
- The UI should show branches and backtracking, not just the final answer.
- A "thought" should be a compact action/state unit, not a long essay.

### LATS - Language Agent Tree Search

Source: [Language Agent Tree Search Unifies Reasoning Acting and Planning in Language Models](https://arxiv.org/abs/2310.04406), ICLR 2024.

LATS combines MCTS with language agents, value functions, environment feedback, and self-reflection. It uses selection, expansion, evaluation, simulation, backpropagation, and reflection. The important addition is external feedback: the agent can interact with an environment, learn from failed trajectories, and store reflections in memory.

LATS is the closest match to a sub-agent story:

- agent proposes actions
- value function scores states
- environment returns observations
- reflection module explains failure and proposes alternatives
- memory stores failed trajectories and reflections

ReasonTree implication:

- Our four roles - proposer, simulator, scorer, critic - are research-aligned.
- For code, tests are the environment.
- For chess, legal-line/mate verifier is the environment.
- For project decisions, constraints and risk checks act as a weaker environment.
- Reflection should be used after failure, not on every node.

### No Train Still Gain

Source: [No Train Still Gain. Unleash Mathematical Reasoning of Large Language Models with Monte Carlo Tree Search Guided by Energy Function](https://arxiv.org/abs/2309.03224), 2023.

This paper uses MCTS with a lightweight energy function to rank mathematical reasoning steps. The central move is to add a path verifier/scoring mechanism instead of relying only on the base model's token probabilities.

ReasonTree implication:

- A scorer can be a small specialized function, not another frontier model.
- For public demos, a simple verifier is more convincing than a long hidden prompt.
- "MCTS with weak reward" is fragile; "MCTS with task-grounded reward" is much stronger.

### MCTS-DPO

Source: [Monte Carlo Tree Search Boosts Reasoning via Iterative Preference Learning](https://arxiv.org/abs/2405.00451), 2024.

This paper uses MCTS to collect preference data and break instance-level rewards into step-level signals. It then trains the model with DPO using MCTS-generated preference data.

ReasonTree implication:

- Search is useful not only at inference time, but also for producing training data.
- ReasonTree outputs should save branch traces, scores, runner-up branches, and failure checks.
- Later, this repo could produce small preference datasets from verified examples.

### rStar

Source: [Mutual Reasoning Makes Smaller LLMs Stronger Problem-Solvers](https://arxiv.org/abs/2408.06195), 2024.

rStar uses self-play mutual reasoning. One small model generates reasoning trajectories with MCTS and human-like reasoning actions. Another similar model acts as discriminator/verifier. Trajectories accepted by both are treated as more likely correct.

ReasonTree implication:

- Parallel agents do not need to be different model families. They can be different roles or prompts.
- A generator/discriminator pair maps cleanly to proposer/critic.
- Mutual consistency can be a fallback when no hard verifier exists.

### DeepSeek-Prover-V1.5

Source: [DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback for Reinforcement Learning and Monte-Carlo Tree Search](https://arxiv.org/abs/2408.08152), 2024.

DeepSeek-Prover-V1.5 uses proof assistant feedback and an MCTS variant for formal theorem proving in Lean 4. This is an important example because the verifier is not subjective. Lean either accepts a proof state or it does not.

ReasonTree implication:

- The best demos should use hard verifiers: tests, parsers, theorem provers, chess legality, SAT/SMT solvers, schema validators.
- For code examples, tests should score branches.
- For chess examples, a mate verifier should score branches.

### SC-MCTS*

Source: [Interpretable Contrastive Monte Carlo Tree Search Reasoning](https://arxiv.org/abs/2410.01707), 2024.

SC-MCTS* focuses on a weakness of LLM MCTS: speed. It argues that prior MCTS reasoning work often under-studied speed and reward quality. The paper introduces contrastive reward modeling, speculative decoding for faster node evaluation, improved UCT, and improved backpropagation.

ReasonTree implication:

- Speed and reward quality should be treated as first-class product concerns.
- The default workflow should be shallow and cached.
- Do not use classic MCTS iteration counts blindly. LLM calls are expensive.
- It is better to expand fewer high-value nodes than to revisit the same prompt many times.

### LE-MCTS

Source: [Ensembling Large Language Models with Process Reward-Guided Tree Search for Better Complex Reasoning](https://arxiv.org/html/2412.15797v1), 2024.

LE-MCTS treats step-by-step reasoning with multiple language models as a Markov decision process. A state is the intermediate reasoning path. An action is choosing a model from a pool to generate the next reasoning step. A process reward model scores intermediate steps.

This is directly relevant to sub-agent and parallel-agent design:

- each branch can be generated by a different model or prompt role
- a process reward model ranks steps
- optimistic backpropagation can prefer a parent if at least one child is strong

ReasonTree implication:

- The tree node can store `agent_id` or `model_id`.
- Parallel branches can be produced by different prompts: conservative, creative, skeptical, verifier-aware.
- Backpropagation should probably be optimistic for user workflows: one strong path is enough.

### AlphaLLM-CPL

Source: [Towards Self-Improvement of LLMs via MCTS: Leveraging Stepwise Knowledge with Curriculum Preference Learning](https://arxiv.org/html/2410.06508v1), 2024.

AlphaLLM-CPL extracts trajectory pairs from MCTS search trees, including child nodes that share the same parent, and uses curriculum preference learning to distill MCTS behavior into the LLM.

ReasonTree implication:

- Sibling comparisons are valuable. Do not only save the winning path.
- For each node, save why one branch beat another.
- This can become a dataset format: `state`, `chosen_action`, `rejected_action`, `score_gap`, `verifier_result`.

### rStar-Math

Source: [rStar-Math: Small LLMs Can Master Math Reasoning with Self-Evolved Deep Thinking](https://arxiv.org/html/2501.04519v1), 2025.

rStar-Math uses MCTS rollouts to synthesize verified math reasoning trajectories. It generates a one-step chain-of-thought plus Python code at each step, keeps nodes with successful code execution, and uses MCTS Q-values to label intermediate step quality.

ReasonTree implication:

- For math/data/code tasks, ask branches to produce executable checks.
- Keep only branches that pass cheap validation.
- Use Q-values or normalized scores as training labels later.

### REKG-MCTS And Knowledge-Graph MCTS

Source: [REKG-MCTS: Reinforcing LLM Reasoning on Knowledge Graphs](https://aclanthology.org/2025.findings-acl.484.pdf), 2025.

This line applies MCTS to knowledge graph reasoning. The high-level pattern is dynamic path exploration where the LLM helps select or interpret paths, while graph structure constrains the search.

ReasonTree implication:

- For research synthesis and data diagnostics, a graph of facts, claims, tables, tools, or entities can serve as the state space.
- The LLM should not invent the graph. It should navigate and score graph-grounded branches.

## What This Means For ReasonTree

### Use MCTS-Inspired Search, Not Naive Classic MCTS

Classic MCTS repeatedly visits nodes to estimate values through stochastic rollouts. In LLM workflows, each visit may be a costly model call. Repeating the exact same prompt is usually wasteful unless the generator is intentionally stochastic and cached.

ReasonTree default should be:

- depth: 3
- branch width: 3
- beam width: 1-2
- expand each node once
- cache node outputs
- early stop on terminal verified solution
- use MCTS-style scoring/backpropagation only when there is a real value estimate to update

Use full UCT-style visits only when:

- branch generation is stochastic
- each call is cheap enough
- there is a hard verifier or process reward model
- results are cached
- repeated samples can materially improve confidence

### Role Architecture

ReasonTree can map papers into a practical sub-agent design:

- Orchestrator: owns tree, budget, cache, stop conditions.
- Proposer: generates 3-5 candidate actions for a state.
- Simulator/world model: predicts next state or required follow-up.
- Scorer: uses verifier, tests, PRM, or rubric.
- Critic/discriminator: stress-tests the selected path.
- Reflector: only runs after failed terminal states.

The key product decision: the orchestrator should be deterministic and auditable. Agents can be stochastic; the tree controller should not be.

### Parallel Branch Execution

Parallelism is useful at expansion time:

1. Orchestrator selects frontier nodes.
2. For each selected node, spawn proposer calls in parallel or one proposer call returning multiple branches.
3. Run branch verifiers in parallel.
4. Score results.
5. Keep top branches.
6. Record losers for later preference data.

For Claude Code subscription users, this must be budget-aware. Parallel calls can multiply cost quickly. The safer default is one model call that returns multiple candidate branches, then parallel local verification when available.

### Why Verifiers Matter

Across the papers, the strongest systems avoid pure self-evaluation:

- LATS uses environment feedback.
- DeepSeek-Prover uses Lean feedback.
- rStar uses a discriminator model.
- rStar-Math uses code execution and process preference models.
- LE-MCTS uses a process reward model.
- No Train Still Gain uses an energy function.

For ReasonTree, the public demos should therefore be verifier-first:

- Chess: FEN plus mate verifier.
- Code: unit tests.
- Data analysis: SQL checks or invariants.
- Project planning: constraints, deadlines, reversibility, risk matrix.
- Planning and decision practice: constraints, reversibility, regret risk, and user priorities.

### Dataset Opportunity

ReasonTree can save more than final answers:

```json
{
  "problem_id": "example",
  "state": "partial state",
  "candidate_actions": ["A", "B", "C"],
  "chosen_action": "B",
  "rejected_actions": ["A", "C"],
  "scores": {"A": -0.2, "B": 0.8, "C": 0.1},
  "verifier": "unit_tests",
  "verifier_result": "pass",
  "principal_path": ["B", "B1", "B1a"],
  "failure_check": "what could invalidate the answer"
}
```

This format can support:

- Medium article evidence
- GitHub demo traces
- small preference datasets
- future DPO-style or ranker training
- regression tests for the skill

## Recommended ReasonTree Positioning

Use this language:

> ReasonTree is an MCTS-inspired state-action search-time reasoning workflow for Claude. It externalizes reasoning into a bounded tree, uses model calls to propose and simulate branches, and uses verifiers or explicit scorers to select an auditable path.

Avoid this language:

> ReasonTree makes any model smarter.

Use this instead:

> ReasonTree can improve reliability on tasks where one-shot answers are brittle and where candidate branches can be scored or verified.

## Implementation Guidance

For the current repo:

1. Keep the chess demo, but explain it as verifier-backed search.
2. Remove inflated visit counts from the demo trace.
3. Prefer "score" over "visits" in the visual report.
4. Add cache keys for every state/action/model prompt.
5. Add `agent_id` to branch metadata later.
6. Keep default depth 3 and branch width 3.
7. Allow max depth 5 only when the user explicitly opts in.
8. Add a JSON trace export format that can become preference data.

The practical ReasonTree algorithm should be closer to "budgeted best-first tree search with optional MCTS backpropagation" than to naive classic MCTS.
