# ReasonTree case study

## The claim

ReasonTree is not a generic IQ booster. It is a provider-neutral verification controller and bounded-search fallback for cases where a one-shot agent trusts a plausible answer before checking it, or spends an unpredictable amount of inference on one opaque attempt.

The measured claim is deliberately narrow:

> Run the cheapest deterministic check first, use one fast subscription model to explain the evidence, and escalate to a deeper tree only when the checked counterexample branch does not resolve the task.

## Rated chess holdout: executable state transitions

The 2026-07-13 benchmark is the strongest current positive result. A 50-case manifest was frozen from the official Lichess CC0 puzzle database. The first 25 cases were used to tune one bounded chess configuration; the remaining 25 were held out.

| Condition | Holdout result | Median wall time |
| --- | ---: | ---: |
| Haiku direct text, no tools, 30s cap | 1/25 | 30.02s |
| bounded state-action adapter | 21/25 | 5.70s |

The first ten holdout cases where raw Haiku failed and the adapter succeeded were run through the full adapter + Haiku explanation path. All 10 returned the correct move in 8.12-21.47 seconds. This is a presentable rescue set, but the full 1/25 versus 21/25 matrix is the unbiased comparison.

Separate long-run raw telemetry trials returned no usable move on all ten after 102-180 seconds. Six emitted final cost metadata; across those six matched cases, adapter + Haiku was 9.6x faster, 4.65x cheaper, and used 19.8x fewer model output tokens. Four raw costs remain unknown because the CLI emitted no final usage before the external cap.

The result changed the architecture. A prompt-only “think in a tree” smoke timed out just like the raw call. The improvement came from moving board states, legal actions, adversarial replies, scoring, and stop rules into executable code. See [the full rated protocol](CHESS_BENCHMARK.md).

## Everyday showcase: correlated security alerts

A company sees a 1% phishing base rate. Two scanners each have 90% sensitivity and a 5% false-positive rate. Both flag one email. They share code and training data, and no joint-error measurement is available. The task nevertheless demands one exact probability.

The exact probability is not identifiable. With only marginal rates, the joint true-positive and false-positive rates must satisfy Fréchet bounds:

```text
0.80 <= P(both flag | phishing) <= 0.90
0.00 <= P(both flag | legitimate) <= 0.05
```

Those admissible extremes imply a posterior range of approximately 13.9% to 100%. Conditional independence produces 76.6%, but that is one unproven interior scenario, not a bound.

The reproducible input is `examples/correlated-alerts.json`. On 2026-07-12:

| Condition | Outcome | Operational result |
| --- | --- | --- |
| Haiku 4.5, one prompt | wrong | returned an unsupported ~15% point estimate and incorrectly bounded the answer at 15%-77% |
| Haiku, agent-only `reasontree-deep` | wrong | consumed about 33k output tokens over roughly six minutes and invented a 20% estimate |
| Haiku, deterministic `reasontree-check` | correct | 9.96s, 960 output tokens, $0.014 CLI cost equivalent |
| GPT-5.6 Luna, one prompt | correct | rejected false precision and computed the 13.9%-100% range |
| GPT-5.6 Luna, deterministic `reasontree-check` | correct | 4.86s; same authoritative verifier evidence |

The result is not “ReasonTree makes every small model smarter.” Luna already solved this cell. The finding is architectural: weak-model prompting and multi-agent debate do not guarantee verification; a deterministic controller can.

Run it through either logged-in subscription CLI:

```bash
.venv/bin/reasontree-check \
  --provider claude --model haiku \
  --case-file examples/correlated-alerts.json --json

.venv/bin/reasontree-check \
  --provider codex --model gpt-5.6-luna \
  --case-file examples/correlated-alerts.json --json
```

## Reproducible chess cases

Both positions are mate-in-two compositions with a unique first move. Ground truth is checked locally with `scripts/chess_mate_search.py` and `python-chess`.

### Case 1: Grimshaw interference

```text
FEN: 8/B2K3Q/5p2/3k4/2p2P2/p6p/r7/b7 w - - 0 1
Solution: 1. Qb1
```

The queen retreats from h7 to b1. Black has 14 legal defenses; every defense has a distinct mating reply. The move is difficult to accept from visual intuition because it moves the queen away from the king and relies on interference between Black's rook and bishop.

### Case 2: forced promotion

```text
FEN: 6k1/5pPp/4pPQP/3pP3/2pP4/1pP5/pP5K/R7 w - - 0 1
Solution: 1. Qb1 axb1=Q/R/B/N 2. Ra8#
```

White offers the queen on b1. Black's only legal replies are the four promotions on b1; every promotion is met by `Ra8#`.

Verify them locally:

```bash
.venv/bin/python scripts/chess_mate_search.py \
  --fen '8/B2K3Q/5p2/3k4/2p2P2/p6p/r7/b7 w - - 0 1' \
  --mate-in 2

.venv/bin/python scripts/chess_mate_search.py \
  --fen '6k1/5pPp/4pPQP/3pP3/2pP4/1pP5/pP5K/R7 w - - 0 1' \
  --mate-in 2
```

## Chess subscription snapshot

This is a single-run operational snapshot from 2026-07-12, not a statistical benchmark. It used Claude Code 2.1.207 through a Claude Max subscription, `--effort medium`, the current aliases `haiku` and `sonnet`, and no API key. Baselines ran in safe mode with default built-in tools; ReasonTree ran the project `reasontree-deep` workflow. Dollar values are Claude CLI cost equivalents reported in JSON, not an additional charge to the subscription.

| Model and case | Mode | Result | Time | Output tokens | CLI cost equivalent |
| --- | --- | --- | ---: | ---: | ---: |
| Haiku 4.5, Grimshaw | one-shot agent | no usable answer before manual 342s cap | 342s wall | 16,329 | $0.125 |
| Haiku 4.5, Grimshaw | `reasontree-deep` | `Qb1`, all 14 defenses verified | 84s wall | 7,388 | $0.112 |
| Sonnet 5, forced promotion | one-shot agent | `Qb1`, verified | 206s wall | 17,587 | $0.611 |
| Sonnet 5, forced promotion | `reasontree-deep` | `Qb1`, verified; caught and repaired a verifier bug | 132s API time | 11,642 | $0.746 |

The Haiku run is the clean showcase: the bounded workflow returned a checked answer in roughly one quarter of the wall time and less than half the output tokens. The Sonnet run is the necessary negative control: the workflow used fewer output tokens and less reported API time, but its multiple calls cost more overall and did not improve correctness.

Other one-shot results in the same snapshot also matter. Sonnet solved Grimshaw in 61 seconds and Haiku solved the forced-promotion case in 163 seconds after writing/checking a solver. Model behavior therefore depends on model version, tool policy, prompt, runtime, and date. A frozen old failure must not be presented as a permanent model limitation.

## Exploratory benchmark record

Earlier experiments were useful mainly because they falsified the broad pitch.

| Evaluation | Outcome | Interpretation |
| --- | --- | --- |
| Four native verifiable tasks, Haiku | one-shot 2/4; verifier-bearing tournament and verify 4/4 | positive small-suite evidence for forced verification |
| Four native verifiable tasks, Sonnet | one-shot 2/4; verify 4/4 | positive small-suite evidence, but single-run cost was noisy |
| AIME 2026 with tools, Haiku | one-shot 28/29; ReasonTree 26/29 | tree added schema/protocol failure surface |
| AIME 2026 with tools, Sonnet | one-shot 28/29; ReasonTree 28/29 | no accuracy uplift; one-shot nearly saturated |
| AIME 2026 without tools, Haiku | one-shot 24/29; matched sampling 26/29; ReasonTree 23/29 | matched-compute sampling beat the tree |
| ARC-AGI-2 five-task pilot, Sonnet | one-shot 2/5; ReasonTree 3/5; matched sampling 4/5 | extra inference helped, but the tree did not beat the control |

These are exploratory runs, not publication-grade estimates: most conditions used one trial, some cells had infrastructure failures, and exact token costs include retry noise. Their value is directional. They reject the claim that explicit tree search generically makes a tool-using model smarter.

## What transfers beyond chess

Chess remains useful because verification is objective and visual. The reusable pattern is broader:

- coding: run tests or a minimal reproduction before accepting a repair;
- planning: verify dates, capacities, dependencies, and hard constraints before committing;
- research: separate sourced facts from assumptions and require source checks for terminal claims;
- data work: recompute a metric and reconcile definitions before explaining a movement;
- decisions: use adversarial refutation when no mechanical verifier exists, and label the result unverified.

The controller should stop after the cheapest authoritative check. Multi-agent search is an escalation path, not mandatory ceremony.

## Resume-safe description

> Built ReasonTree, an open-source bounded state-action controller and skill for Claude Code and Codex subscription CLIs; on a frozen 25-puzzle Lichess holdout, raw Haiku produced 1/25 usable solutions under a 30-second cap while the executable adapter solved 21/25, with 10/10 selected failures rescued end-to-end through adapter + Haiku explanations; broader AIME/ARC controls documented where extra tree inference did not help.
