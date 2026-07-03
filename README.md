<div align="center">

# ReasonTree

**A search-time reasoning skill for making Claude branch, score, verify, and synthesize before it answers.**

*One prompt is a guess. A small tree is a workflow.*

[![Skill](https://img.shields.io/badge/skill-general_state--action_reasoning-111827)](.claude/skills/reasontree/SKILL.md)
[![Demo](https://img.shields.io/badge/demo-chess_mate--in--2-0f766e)](#demo)
[![Default](https://img.shields.io/badge/default-depth_3_width_3-2563eb)](#how-it-works)
[![Max](https://img.shields.io/badge/max-depth_5_width_5-7c3aed)](#how-it-works)

</div>

ReasonTree turns a brittle one-shot prompt into a bounded state-action tree: separate facts from assumptions, propose candidate actions, simulate next states, score branches, expand the most promising path, and synthesize an auditable answer.

The skill is general. It is meant for problems where a model should compare options before committing: planning, coding, research synthesis, risk decisions, writing strategy, and other multi-step tasks where a fluent first answer can be too shallow.

It can help smaller or cheaper models by moving part of the intelligence into the workflow: branch, simulate, score, verify. Stronger models can also benefit because the same scaffold forces the model to expose candidate paths, assumptions, and failure modes instead of hiding everything inside one completion.

The first public demo is chess because the answer can be checked cleanly. ReasonTree is not a chess engine; chess is the microscope.

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

| Run | Result |
| --- | --- |
| Sonnet 5 one-shot, structured output, effort medium | Did not complete within the 75s local eval window |
| Opus 4.8 one-shot, structured output, safe mode, effort medium | Did not complete within the 90s local eval window |
| ReasonTree skill + tools + repo-local verifier | Returned `Bxg5+ Kxg5 Qf4#` |

| Without ReasonTree | With ReasonTree: step 1 | With ReasonTree: step 2 | With ReasonTree: mate |
| --- | --- | --- | --- |
| ![Start position](assets/chess/reasontree-ch-01-start.svg) | ![Bxg5+](assets/chess/reasontree-ch-01-step-1-bxg5.svg) | ![Kxg5](assets/chess/reasontree-ch-01-step-2-kxg5.svg) | ![Qf4 mate](assets/chess/reasontree-ch-01-step-3-qf4-mate.svg) |
| direct run did not complete in local eval window | `1. Bxg5+` | `1... Kxg5` | `2. Qf4#` |

The full five-position puzzle set is in [docs/chess_puzzle_set.md](docs/chess_puzzle_set.md).

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
cd reason-tree
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Claude Code must already be installed and authenticated on the machine running the CLI.

## Use The Skill

From this repo in Claude Code:

```text
/reasontree <your task>

Include the goal, known facts, assumptions or beliefs, hard constraints, success criteria, and any verifier that can check candidate answers.
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

For the deterministic public demo:

```bash
PYTHONPATH=src python -m reasontree.cli chess \
  --html demo/reasontree_demo_report.html \
  --log logs/reasontree_demo.jsonl
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
