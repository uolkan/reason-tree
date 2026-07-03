/reasontree Use ReasonTree to solve this chess tactic.

White to move. It is mate in 2.

FEN: 4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1

Use the bounded ReasonTree procedure: propose candidate first moves, check the most promising forcing replies, and verify the selected line. If local tools are available in this repo, use the chess verifier only to check the final line instead of guessing.

Return the best first move in SAN and the principal variation.
