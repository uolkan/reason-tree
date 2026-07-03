# ReasonTree Chess Puzzle Set

Use these positions as the clean public demo set. The model should see only the puzzle prompt during the direct and ReasonTree runs. Keep the answer key hidden until after the run.

Default ReasonTree budget for these demos:

- `max_depth`: 3
- `branch_width`: 3
- `beam_width`: 2
- `max_depth` may be raised to 5 only for harder follow-up tests.

## Demo Prompt

```text
Use ReasonTree to solve this chess tactic.

Position:
FEN: <FEN>
Side to move: <White or Black>
Goal: find the first move of a forced mate in 2.

Search loop:
1. Propose up to 3 candidate first moves.
2. For each candidate, simulate the strongest defensive reply.
3. Expand the most promising branches one more move.
4. Score a branch as successful only if every defensive reply still leads to mate.
5. Return the best first move in SAN plus the principal variation.

Return:
- best_move
- principal_variation
- branch_summary
- failure_check
```

## Puzzles

| ID | Side | FEN | Target |
| --- | --- | --- | --- |
| ReasonTree-CH-01 | White | `4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1` | Mate in 2 |
| ReasonTree-CH-02 | White | `r1bqkbn1/1pppp2r/p4ppp/7Q/2P5/3BP1PN/P2P1P1P/RNB1K1R1 w Qq - 0 9` | Mate in 2 |
| ReasonTree-CH-03 | White | `2bk1r2/3p1p2/4p1N1/7p/2Q5/3PBP2/1P1KPP1P/n2R1B1R w - - 1 24` | Mate in 2 |
| ReasonTree-CH-04 | White | `r1b2b1r/4pppp/4k3/p2p4/Q2p1B2/2N1P1P1/PP3PBP/1R2K1NR w K - 2 15` | Mate in 2 |
| ReasonTree-CH-05 | Black | `rnbqk1nr/5pp1/1p1pp3/p5b1/P4PK1/8/RPP1P3/1N2qBN1 b kq - 0 15` | Mate in 2 |

## Answer Key

| ID | First move | Principal variation |
| --- | --- | --- |
| ReasonTree-CH-01 | `Bxg5+` | `Bxg5+ Kxg5 Qf4#` |
| ReasonTree-CH-02 | `Bxg6+` | `Bxg6+ Rf7 Bxf7#` |
| ReasonTree-CH-03 | `Bb6+` | `Bb6+ Ke8 Qxc8#` |
| ReasonTree-CH-04 | `Qc6+` | `Qc6+ Kf5 Bh3#` |
| ReasonTree-CH-05 | `Qf2` | `Qf2 Ra3 Rh4#` |

## Public Demo Framing

The public story should stay simple:

1. Direct prompt: ask for the first move from one FEN.
2. ReasonTree prompt: ask for the same move using ReasonTree search.
3. Reveal the answer key and compare.

Do not lead with implementation details. The point is the search-time reasoning pattern: branch, simulate, score, expand, verify.
