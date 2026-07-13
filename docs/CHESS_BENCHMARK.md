# Rated chess benchmark: frozen holdout

## Verdict

On a frozen 25-puzzle Lichess holdout in the 1809-1819 rating slice, raw Haiku solved 1/25 within a 30-second operational cap. The bounded ReasonTree chess adapter solved 21/25 under a 12-second search cap.

The paired result was:

| Outcome | Cases |
| --- | ---: |
| both correct | 1 |
| ReasonTree only | 20 |
| raw Haiku only | 0 |
| both failed | 4 |

This is the first result in this project that supports a concrete 10-puzzle rescue demo. It does **not** show that a prompt-only reasoning tree is a universal model upgrade. The improvement came from externalizing state transitions into a small executable adapter.

The machine-readable manifest is [`benchmarks/chess/lichess_1800_2000_v1.json`](../benchmarks/chess/lichess_1800_2000_v1.json). The complete paired summary is [`benchmarks/chess/results/2026-07-13-haiku-holdout.json`](../benchmarks/chess/results/2026-07-13-haiku-holdout.json).

## Protocol

The source was the official [Lichess open puzzle database](https://database.lichess.org/), released under CC0. Lichess ratings are empirical puzzle ratings, not a direct conversion to human FIDE Elo.

Selection was frozen before the holdout run:

- scan the first 500 source rows satisfying rating 1800-2000;
- require rating deviation at most 80, popularity at least 85, and at least 200 plays;
- keep solutions with 3-7 UCI plies including the setup move;
- sort by `(rating, puzzle_id)` and keep the lowest-rated 50;
- use the first 25 for development and the remaining 25 as untouched holdout.

This produced a deliberately narrow set: development ratings 1800-1809 and holdout ratings 1809-1819.

### Primary direct baseline

- Claude Code 2.1.207 through a Claude Max subscription;
- model alias `haiku`, resolved to `claude-haiku-4-5-20251001`;
- low effort, built-in tools disabled;
- FEN plus an ASCII board, no legal-move list and no answer key;
- request exactly one UCI move as plain text;
- 30-second wall cap per puzzle.

The plain-text condition matters. An earlier JSON-schema baseline also timed out, but structured output can introduce retry behavior, so it is not the primary comparison.

### Bounded chess adapter

The adapter never reads the Lichess solution during inference. It:

1. parses the position with `python-chess`;
2. enumerates legal actions and real successor states;
3. orders checks, captures, and promotions before quiet moves;
4. searches adversarial replies with depth-4 negamax plus depth-3 quiescence;
5. scores checkmate, material, and pawn advancement;
6. stops after 300,000 nodes or 12 seconds;
7. exposes the top three principal variations;
8. optionally asks Haiku once to explain the selected branch.

The configuration was tuned only on the 25 development cases, where it reached 20/25, then frozen before opening the holdout.

## Full holdout result

| Condition | Correct | Accuracy | Mean wall time | Median wall time |
| --- | ---: | ---: | ---: | ---: |
| raw Haiku, direct text | 1/25 | 4% | 29.80s | 30.02s |
| bounded tree, local | 21/25 | 84% | 6.52s | 5.70s |

Raw Haiku timed out on 24/25 cases. A timeout means “no usable move inside the operational cap,” not “the model could never solve this puzzle.”

Six bounded-tree cases reached the 12-second cap before every root action received a complete depth-4 score. The controller returned the best fully evaluated root branch available; five of those six predictions were correct. The machine-readable result exposes this as `tree_completed_full_root` instead of presenting every search as exhaustive.

## Ten presentable rescue cases

The showcase uses the first ten holdout cases, in frozen order, where raw Haiku failed and the bounded tree succeeded. This table is a conditional demo; the 1/25 versus 21/25 full holdout is the unbiased comparison.

| Puzzle | Rating | Move | Raw Haiku | Tree + Haiku time | CLI cost equivalent | Haiku output tokens |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| 03kkE | 1809 | `b3d5` | timeout | 21.47s | $0.0068 | 1,029 |
| 04E5q | 1809 | `g3g7` | timeout | 17.45s | $0.0150 | 730 |
| 01SN2 | 1810 | `d4c5` | timeout | 9.92s | $0.0148 | 691 |
| 04Sku | 1810 | `c6e5` | timeout | 21.28s | $0.0141 | 544 |
| 036Ew | 1811 | `c1c6` | timeout | 16.67s | $0.0147 | 665 |
| 05lF8 | 1811 | `c7c4` | timeout | 11.03s | $0.0146 | 643 |
| 02D70 | 1812 | `b7b2` | timeout | 13.27s | $0.0135 | 415 |
| 02rnR | 1812 | `e2g4` | timeout | 14.85s | $0.0155 | 812 |
| 01qBb | 1813 | `b6d7` | timeout | 10.83s | $0.0144 | 599 |
| 02Uju | 1813 | `h3h7` | timeout | 8.12s | $0.0139 | 500 |

ReasonTree + Haiku was 10/10 on this rescue set. Mean total wall time was 14.49 seconds, mean CLI cost equivalent was $0.0137, and mean Haiku output was 663 tokens. Haiku repeated the controller-selected move in every case; the controller never had to override it.

## Speed and cost boundaries

The rescue set proves a latency/availability advantage under the chosen cap: every ReasonTree answer arrived in 8.12-21.47 seconds, while every direct call reached 30 seconds without a move.

The 30-second calls did not emit final usage metadata, so a separate long-run telemetry trial was run on the same ten prompts. All ten raw calls still produced no usable move after 102-180 seconds. Six emitted a final budget envelope; four reached the 180-second external cap without cost metadata.

For the six cases with matched final telemetry:

| Six-case matched total | Wall time | Output tokens | CLI cost equivalent |
| --- | ---: | ---: | ---: |
| raw Haiku, no usable answers | 804.27s | 75,772 | $0.4071 |
| bounded tree + Haiku, 6/6 correct | 83.56s | 3,828 | $0.0876 |

On those measurable cases, the controller was 9.6x faster, used 19.8x fewer model output tokens, and was 4.65x cheaper. The ratio applies to six cases, not all ten; the other four raw calls have unknown final cost.

There is one clean efficiency control where both methods completed correctly:

| Puzzle 00lHu | Wall time | Output tokens | CLI cost equivalent |
| --- | ---: | ---: | ---: |
| raw Haiku | 24.52s | 2,220 | $0.01572 |
| bounded tree + Haiku | 11.36s | 704 | $0.01487 |

On that case, the controller was about 2.2x faster, used 3.2x fewer model output tokens, and was slightly cheaper. All long-run probe rows and matched metrics are embedded in the machine-readable holdout result.

## What “human-like tree thinking” means here

The defensible analogy is externalized working memory, not a claim that the system recreates human cognition.

- the board is an explicit state;
- legal moves are explicit actions;
- each action creates a real successor state;
- the opponent supplies an adversarial counter-branch;
- candidates are compared under a fixed budget;
- the winning line remains visible and replayable.

The failed prompt-only smoke is important: raw Haiku and a one-call “build a tree” prompt both failed to return the first development puzzle inside 45 seconds. A verbal instruction to reason in branches was not enough. The gain appeared when the controller made state transitions executable and bounded.

## What transfers beyond chess

Chess is the microscope, not the product. A ReasonTree adapter needs five domain-specific operations:

```text
state -> candidate actions -> executable transition -> score/check -> stop rule
```

Examples:

- code repair: repository state -> patches -> apply in a worktree -> tests -> test/time budget;
- scheduling: calendar state -> candidate slots -> timezone conversion -> constraint check -> first feasible slot;
- research: claim ledger -> hypotheses -> source retrieval -> evidence score -> confidence threshold;
- decisions: facts -> options -> consequence scenarios -> constraint/regret score -> bounded recommendation.

When transitions or checks cannot be made authoritative, the result must be labeled heuristic or unverified. Prompted branches alone should not be called verification.

## Reproduce

Install the package:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The frozen manifest is already committed. The official download URL is mutable, so a later download may not reproduce the same IDs; the committed manifest is the benchmark source of truth. To run the selector against the current Lichess export, stream the decompressed CSV:

```bash
curl -L https://database.lichess.org/lichess_db_puzzle.csv.zst \
  | unzstd -q -c \
  | PYTHONPATH=src .venv/bin/python scripts/prepare_lichess_benchmark.py \
      --output benchmarks/chess/lichess_1800_2000_v1.json \
      --scan-qualifying 500 --limit 50 --development-count 25
```

Run the primary direct holdout. This invokes 25 subscription-model calls and can take several minutes:

```bash
.venv/bin/reasontree-chess-eval \
  --manifest benchmarks/chess/lichess_1800_2000_v1.json \
  --output runs/holdout-direct.jsonl \
  --provider claude --model haiku --effort low \
  --condition direct-text --offset 25 --limit 25 \
  --timeout-s 30 --max-output-tokens 600
```

Run the local bounded tree without a model call:

```bash
.venv/bin/reasontree-chess-eval \
  --manifest benchmarks/chess/lichess_1800_2000_v1.json \
  --output runs/holdout-tree.jsonl \
  --condition tree --offset 25 --limit 25 \
  --tree-depth 4 --tree-quiescence-depth 3 \
  --tree-max-nodes 300000 --tree-timeout-s 12
```

The benchmark CLI resumes existing JSONL outputs by puzzle, provider, model, and condition. Use `--no-resume` only when an intentional fresh trial is required.

## Independent reproduction

A second, separate session re-verified this benchmark on 2026-07-13 without reusing any cached results:

- the bounded tree was re-run on all 25 frozen holdout puzzles and reproduced 21/25 exactly, with the same four misses (`00Yuf`, `00G1l`, `01B8h`, `01kUF`);
- five puzzle IDs were checked against the live Lichess API: all five first solution moves matched the frozen manifest (live ratings drift slightly because Lichess re-rates puzzles as they are played; the manifest pins the 2026-07-01 export);
- a fresh 5-case raw Haiku direct-text run returned 0/5 (four timeouts, one wrong move), consistent with the frozen 1/25;
- two rescue cases were re-run through the full tree + Haiku explanation path: 2/2 correct, and the controller never had to override the model;
- the prompt-only `reasontree` condition (Haiku builds the tree itself, ledger included) was re-tested on two rescue cases: 0/2, both hit a 90-second cap, confirming the gain is architectural rather than prompt wording;
- the full unit test suite passed (21/21).

## Limitations

- This is a small 25-case holdout from one narrow Lichess slice.
- The result uses one dated Haiku subscription snapshot and one trial per condition.
- Lichess rating is not a stable statement about a model’s maximum “Elo.”
- The chess adapter is intentionally small and still missed 4/25 holdout cases.
- Six searches returned a partial root frontier at the time cap; an iterative-deepening v2 should guarantee a complete shallower frontier before deepening.
- The 10-case table is selected from paired holdout outcomes; it is a demo, not a separate accuracy estimate.
- Broader AIME and ARC experiments in this repository did not show a general reasoning uplift over matched-compute controls.

The public claim should therefore be:

> On a frozen rated chess holdout, a small executable state-action adapter turned a slow, mostly non-responsive Haiku baseline into a fast 21/25 solver, while preserving visible branches and strict compute limits. Whether that transfers depends on building an equally real adapter for the target domain.
