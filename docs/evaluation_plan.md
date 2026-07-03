# Evaluation Plan

The repo should not claim "Model X cannot solve this puzzle" until raw evidence is captured.

## Fixed Inputs

For each puzzle:

- puzzle id
- FEN
- side to move
- natural-language prompt
- expected SAN or UCI move
- principal variation answer key
- rating bucket
- themes

The prompt shown to the model must not include the answer key. Reveal the expected move only after the direct and workflow runs are saved.

## Baselines

1. Direct answer: ask the model for one move only.
2. Direct answer with brief explanation.
3. Best-of-N direct answers with majority vote.
4. ReasonTree: propose actions, simulate replies, score branches, select best path.

## Required Metadata

For every run, save:

- model name and version
- provider
- date
- temperature and reasoning effort
- prompt
- raw output
- parsed answer
- correctness
- latency
- approximate token cost

## Reported Metrics

- top-1 move accuracy
- legal move rate
- parse success rate
- median latency
- median cost
- failure examples
- cases where ReasonTree made the answer worse

## Public Claim Threshold

Use conservative language unless the evaluation has at least:

- 30 puzzles per rating bucket
- fixed prompts
- raw outputs checked into `evals/`
- one direct baseline and one ReasonTree run under the same model family
