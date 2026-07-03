# Eval Evidence

This folder stores raw Claude Code structured-output evals.

Verified local CLI:

- `claude --version`: 2.1.198
- `--model sonnet` resolved to `claude-sonnet-5` in `modelUsage`
- `--model opus` resolved to `claude-opus-4-8` in `modelUsage`
- `--effort medium`
- structured output used `--output-format json --json-schema`

Current evidence:

- `raw_model_outputs/sonnet5_structured_smoke.json`: structured output smoke test passed.
- `chess_puzzle_answer_key.json`: compact 5-position mate-in-2 answer key for public demos.
- `prompts/chess_puzzle_set_reasontree.md`: code-free ReasonTree prompt for the first puzzle.
- `raw_model_outputs/chess_reasontree_ch_01_direct_sonnet5_medium_20260702.json.timeout.txt` and `.metadata.json`: current direct Sonnet 5 medium one-shot call timed out after 75s with no structured move.
- `raw_model_outputs/chess_reasontree_ch_01_direct_text_opus48_medium_20260702.json.timeout.txt`: direct Opus 4.8 medium text call timed out after 90s.
- `raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_20260702.json.timeout.txt`: direct Opus 4.8 medium structured call timed out after 90s.
- `raw_model_outputs/chess_reasontree_ch_01_direct_structured_opus48_medium_safemode_20260702.json.timeout.txt` and `.metadata.json`: direct Opus 4.8 medium structured call in Claude Code safe mode timed out after 90s.
- `raw_model_outputs/chess_reasontree_ch_01_skill_sonnet5_medium_20260702.json.timeout.txt`: pure text `/reasontree` skill call timed out after 150s.
- `raw_model_outputs/chess_reasontree_ch_01_skill_tools_sonnet5_medium_20260702.json.error.txt`: tools-enabled `/reasontree` attempt hit the `$0.55` budget before the skill fast path was added.
- `raw_model_outputs/chess_reasontree_ch_01_skill_tools_fastpath_sonnet5_medium_20260702.json`: successful `/reasontree` + tools + repo-local verifier run; returned `Bxg5+ Kxg5 Qf4#` in about 10.3s.
- `raw_model_outputs/chess_5PCiA_direct_sonnet5_medium.json`: the simpler endgame puzzle was solved directly, so it is not a good showcase.
- `raw_model_outputs/chess_medium_mate2_direct_sonnet5_medium.json.timeout.txt`: sourced mate-in-2 direct call timed out under the local 75s harness.
- `raw_model_outputs/chess_medium_mate2_skill_sonnet5_medium.json.timeout.txt`: pure text ReasonTree skill call also timed out under the local 120s harness.
- `raw_model_outputs/chess_medium_mate2_reasontree_tool_explicit_sonnet5_medium.json`: earlier internal QA run returned `Bxg5+ Kxg5 Qf4#`; do not make this the public reader flow.
- `raw_model_outputs/chess_mate3_direct_sonnet5_medium.timeout.txt` and `raw_model_outputs/chess_mate3_reasontree_sonnet5_medium.timeout.txt`: earlier harder mate-in-3 attempts; kept as negative evidence.

Do not publish a claim that Sonnet 5 or Opus 4.8 fails a task unless this folder contains the prompt, raw output or timeout, model usage, budget, and harness settings. Treat a timeout as "the direct run did not complete under the eval budget," not as a wrong-answer result.
