Use ReasonTree to solve this chess tactic.

Position:
FEN: 4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1
Side to move: White
Goal: find the first move of a forced mate in 2.

Search loop:
1. Propose up to 3 candidate first moves.
2. For each candidate, simulate Black's strongest defensive reply.
3. Expand the most promising branches one more move.
4. Score a branch as successful only if every defensive reply still leads to mate.
5. Return the best first move in SAN plus the principal variation.

Return JSON:
{
  "best_move": "SAN move",
  "principal_variation": ["move 1", "move 2", "move 3"],
  "branch_summary": ["short branch notes"],
  "failure_check": "what would make this answer wrong"
}
