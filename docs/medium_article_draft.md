# ReasonTree: State-Action Search for More Reliable LLM Reasoning

The most capable models are increasingly used as agents, not just chat boxes.

ReasonTree is a small state-action tree search loop for making Claude reason more deliberately at inference time.

Instead of relying on one answer, it asks the model to name the current state, propose candidate actions, simulate next states, score branches, and synthesize the result.

This suggests a useful question:

> Can I make the model I already have reason more reliably by giving it a better workflow?

That is the idea behind ReasonTree.

## The Problem With One-Shot Answers

For many tasks, a model's first answer is brittle. It may guess. It may miss a tactical move. It may choose the plausible path instead of the forcing path. Asking it to "think step by step" helps sometimes, but the plan still lives inside one conversation turn.

ReasonTree externalizes the plan into a state-action tree.

Instead of one answer, the workflow asks:

1. What is the current state?
2. Which facts, assumptions, beliefs, preferences, and uncertainties matter?
3. What are the candidate actions?
4. What next state follows each action?
5. How should each next state be scored?
6. Which branch deserves deeper search?
7. What does the whole tree teach, not only the winning leaf?

That is not magic. It is just a disciplined scaffold around the model.

## Why Chess Is the First Demo

Chess is useful because it gives labels. Either the selected move matches the puzzle solution or it does not.

My earlier notebooks built an LLM-guided Monte Carlo Tree Search loop for reasoning tasks and chess puzzles. The pipeline prepared more than 549K Lichess puzzle rows with FEN, side-to-move, prompt notation, labels, and puzzle metadata. The search loop evolved through several practical problems: output parsing, non-numeric rewards, terminal-state checks, API instability, and path reconstruction.

The current repo turns that old notebook work into a small, testable public prototype. Chess is not the product. Chess is the microscope: it gives a label, a forcing line, and a way to show the tree visually.

## The Search Loop

ReasonTree has four conceptual workers:

- proposer: generate candidate moves or actions
- simulator: describe the next state after each action
- scorer: rate the resulting state
- critic: check whether the selected path actually satisfies the original problem

In ReasonTree, those roles are coordinated by a Python runner. It behaves like a small team of nested specialists, but the tree controller is explicit: Python owns the search loop, while Claude proposes, simulates, scores, and critiques.

## What the Demo Shows

The chess demo starts with a compact mate-in-2 puzzle set. The first public example is:

`4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1`

In my local Claude Code harness, a direct Sonnet 5 structured-output call on this position timed out under the 75 second budget. A direct Opus 4.8 structured-output call in safe mode also timed out under a 90 second budget. That is not the same as proving either model can never solve it; it means the one-shot runs did not complete inside the local eval windows.

The ReasonTree demo is designed differently. It asks the model to externalize the search: propose candidate first moves, simulate defensive replies, expand the forcing branches, and use a verifier as the scorer. For this position, the verified line is:

`Bxg5+ -> Kxg5 -> Qf4#`

That distinction matters. The lesson is not "say a magic prompt and the model becomes a chess engine." In fact, pure text ReasonTree skill runs also timed out in local tests. The reliable demo path uses `/reasontree` with tools enabled and a repo-local chess verifier as the scorer. The broader lesson is that search-time reasoning becomes easier to inspect when the workflow has a bounded tree, an answer key, and a critic step.

This is intentionally modest. The demo is deterministic so anyone can run the tests without API keys. The real evaluation should compare direct model answers against workflow-assisted answers on a fixed puzzle set, with raw model outputs saved.

## Why This Matters Beyond Chess

The same pattern applies to tasks where one-shot LLM answers are unreliable:

- code repair
- math reasoning
- product planning
- research synthesis
- data-analysis checks
- personal decision practice

The important part is not chess. The important part is turning "be smarter" into a repeatable workflow: state, action, next state, score, branch notes, and tree synthesis.

## Limits

Search costs more tokens. A bad scorer can confidently select the wrong branch. A workflow can overfit to the benchmark. Some tasks do not have reliable state transitions. And using multiple agents does not remove the need for evaluation.

But for brittle problems, a structured search-time scaffold can be better than simply asking the same model once.

## Repo

The repo includes:

- a Python ReasonTree runner
- a labeled puzzle case
- a reusable skill prompt
- Claude-style subagent prompts
- a visual chess walkthrough
- an evaluation plan for direct-vs-workflow model comparisons

The public claim is intentionally conservative:

> Search-time reasoning workflows can improve reliability on problems where one-shot answers are brittle, by forcing the model to propose, branch, score, and select under an auditable contract.
