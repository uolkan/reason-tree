Use ReasonTree search, not a one-shot answer.

Task: White to move. It is mate in 2.
FEN: 4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1

Search constraints:
- max_depth: 2 white moves / black replies as needed
- branch_width: 3
- score +1 only if the line is forced mate in 2; score -1 if black has a defense
- return best first move and the principal variation
