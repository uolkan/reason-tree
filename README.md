# ReasonTree

Model-guided tree search for Claude.

ReasonTree turns a brittle one-shot prompt into a small state-action tree: separate facts from assumptions, propose candidate actions, simulate next states, score branches, expand the most promising path, and synthesize an auditable answer.

It is not a chess engine. Chess is the first visual demo because the answer can be checked cleanly. The same pattern is meant for planning, code repair, research synthesis, finance/risk decisions, and other problems where a single LLM answer is often too shallow.

The default runner is MCTS-inspired rather than naive classic MCTS. It does not repeatedly revisit the same node by default; it expands a bounded set of branches, scores them, keeps a small beam, and stops when a verified path is found.

## Demo

Puzzle:

```text
FEN: 4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1
White to move. Mate in 2.
```

Without ReasonTree, the direct Sonnet 5 structured-output call did not complete inside the local 75 second eval window:
[raw timeout](evals/raw_model_outputs/chess_reasontree_ch_01_direct_sonnet5_medium_20260702.json.timeout.txt),
[run metadata](evals/raw_model_outputs/chess_reasontree_ch_01_direct_sonnet5_medium_20260702.metadata.json).
The same direct structured prompt also timed out with Opus 4.8 in safe mode after 90 seconds:
[raw timeout](evals/raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_safemode_20260702.json.timeout.txt),
[run metadata](evals/raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_safemode_20260702.metadata.json).

With `/reasontree`, tools enabled, and the repo-local verifier used as the scorer, the selected line is:

```text
Bxg5+ Kxg5 Qf4#
```

Raw successful run:
[structured JSON](evals/raw_model_outputs/chess_reasontree_ch_01_skill_tools_fastpath_sonnet5_medium_20260702.json).

| Without ReasonTree | With ReasonTree: step 1 | With ReasonTree: step 2 | With ReasonTree: mate |
| --- | --- | --- | --- |
| ![Start position](assets/chess/reasontree-ch-01-start.svg) | ![Bxg5+](assets/chess/reasontree-ch-01-step-1-bxg5.svg) | ![Kxg5](assets/chess/reasontree-ch-01-step-2-kxg5.svg) | ![Qf4 mate](assets/chess/reasontree-ch-01-step-3-qf4-mate.svg) |
| direct run did not complete in local eval window | `1. Bxg5+` | `1... Kxg5` | `2. Qf4#` |

The full five-position puzzle set is in [docs/chess_puzzle_set.md](docs/chess_puzzle_set.md).

The second demo is a planning/context-ledger example:

```text
Facts: customer impact is high, rollback is easy, refactor risk is medium, deadline is Friday.
Belief: asking for a narrower pilot may look weak.
Preference: choose a low-regret reversible move.
```

Without ReasonTree, the baseline is the tempting one-shot answer: ship the full change now. With ReasonTree, the tree separates facts from assumptions and selects a reversible pilot with rollback and review:

```text
run_reversible_pilot -> pilot_to_small_segment -> launch_pilot_with_rollback_and_review
```

## How It Works

ReasonTree has two user-facing surfaces:

1. Claude Code skill: `/reasontree <task>`
2. Python CLI runner: `reasontree --task "<task>"`

The Python runner is the engine. It owns the tree loop and uses the user's local Claude Code subscription in the background.

Default search budget:

- `max_depth`: 3
- `branch_width`: 3
- `beam_width`: 2
- `max_nodes`: 48
- hard cap: depth 5, branch width 5

## Install

```bash
git clone git@github.com:uolkan/reason-tree.git
cd reasontree
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Claude Code must already be installed and authenticated on the machine running the CLI.

## Use The Skill

From this repo in Claude Code:

```text
/reasontree should I ship a small bug fix today or wait for a larger refactor next week? Constraints: customer impact is high, refactor risk is medium, rollback is easy.
```

From the shell, for the chess demo:

```bash
.venv/bin/python scripts/run_claude_eval.py \
  --prompt evals/prompts/chess_mate2_reasontree_tool.md \
  --schema evals/schemas/move_pv.schema.json \
  --out evals/raw_model_outputs/chess_reasontree_ch_01_skill_tools_sonnet5_medium.json \
  --model sonnet \
  --effort medium \
  --tools default \
  --permission-mode bypassPermissions
```

Use `bypassPermissions` only in a trusted local checkout. It lets Claude Code call the repo-local verifier during the eval.

To use the skill in another Claude Code project, copy:

```text
.claude/skills/reasontree
```

## Use The ReasonTree Runner

The CLI is the recommended reproducible path. It runs the ReasonTree tree loop and calls Claude in the background for branch proposals, simulations, scores, and critic passes.

```bash
reasontree \
  --task-file evals/prompts/chess_puzzle_set_reasontree.md \
  --model sonnet \
  --effort medium \
  --max-depth 3 \
  --branch-width 3 \
  --beam-width 2 \
  --tools "" \
  --out evals/raw_model_outputs/reasontree_chess_reasontree_ch_01.json
```

For the deterministic public demos:

```bash
PYTHONPATH=src python -m reasontree.cli all \
  --html demo/reasontree_demo_report.html \
  --log logs/reasontree_demo.jsonl
```

When `all` is used, logs are split by demo:

```text
logs/reasontree_demo-chess.jsonl
logs/reasontree_demo-planning.jsonl
```

Useful flags:

- `--model`: `sonnet`, `opus`, or a full Claude model name
- `--effort`: `low`, `medium`, `high`, `xhigh`, or `max`
- `--max-depth`: default `3`, maximum `5`
- `--branch-width`: default `3`, maximum `5`
- `--tools ""`: safest default, no Claude tools exposed
- `--tools default`: allow Claude Code default tools for tasks that need local files or tests

## What Is Included

```text
.claude/skills/reasontree/SKILL.md     Claude Code skill
assets/chess/                          README board visuals
docs/architecture.md                   implementation design
docs/reasontree_algorithm_options.md   state-action scoring variants
docs/chess_puzzle_set.md               5 FEN puzzles plus answer key
docs/evaluation_plan.md                eval protocol
docs/llm_mcts_literature_notes.md      LLM tree-search and MCTS paper notes
docs/medium_article_draft.md           article draft
docs/reasontree_design_brainstorm.md   state-action tree-search design
docs/reasontree_use_cases.md           Claude customer/use-case mapping
evals/chess_puzzle_answer_key.json     machine-readable answer key
src/reasontree/reasontree.py           Python model-guided tree controller
tests/                                 regression tests
```

## Claims

Use conservative language. This repo does not claim that every model becomes superhuman at chess or coding.

The defensible claim is:

> Search-time reasoning can improve reliability on brittle tasks by externalizing the answer process into a bounded tree: branch, simulate, score, expand, and verify.

Do not claim that a specific frontier model failed a task unless the raw prompt, model ID, settings, and output are saved under `evals/`. A timeout means the direct run did not complete under the eval budget; it is not the same as a wrong answer.
