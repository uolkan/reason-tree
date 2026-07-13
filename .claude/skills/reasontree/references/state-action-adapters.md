# State-action adapters

Use an executable adapter when the domain exposes real transitions. Do not ask the model to imagine a transition that code, a solver, a test, or a data query can perform.

## Contract

Define five operations:

```text
state
actions(state)
transition(state, action) -> next_state
terminal_score(next_state) or heuristic_score(next_state)
action_id(action)
```

Also set explicit `depth`, `max_nodes`, `timeout`, and cost limits.

The Python contract is `StateActionAdapter` in `src/reasontree/state_search.py`. `BoundedStateSearch` supplies provider-neutral adversarial search. The chess production adapter uses a specialized push/pop implementation for speed and also conforms to the generic contract through `ChessStateAdapter`.

## Verification labels

- `verified`: an authoritative terminal check proved the claim, such as a passing test or checkmate.
- `heuristic`: transitions were real but the scorer is approximate, such as a material evaluation.
- `underdetermined`: multiple fact-compatible states produce different answers.
- `unverified`: neither an authoritative transition/check nor adequate evidence is available.

Never upgrade `heuristic` to `verified` because a model repeats the selected action.

## Adapter examples

### Code repair

```text
state: repository plus failing test
actions: candidate patches
transition: apply patch in isolated worktree
score: test results, regression count, diff size
stop: tests pass or patch/time budget ends
```

### Scheduling

```text
state: participants, calendars, named time zones, constraints
actions: candidate slots
transition: convert and reserve a hypothetical slot
score: hard conflicts first, then preferences
stop: first verified feasible slot or candidate budget ends
```

### Research

```text
state: claim ledger and current sources
actions: retrieve a source, test a counterexample, narrow a claim
transition: update the ledger with cited evidence
score: source authority, directness, contradiction status
stop: evidence threshold, unresolved contradiction, or search budget
```

## Chess benchmark lesson

On the 2026-07-13 development smoke, both raw Haiku and a one-call prompt that requested a tree failed to return the first rated puzzle inside 45 seconds. The executable chess adapter, tuned on 25 development cases and frozen before 25 holdout cases, reached 21/25 on holdout while raw Haiku reached 1/25 under a 30-second cap.

Treat this as evidence for executable domain structure, not for longer prompting or universal model uplift.
