# Architecture

ReasonTree is a Python model-guided tree controller that uses Claude as the reasoning engine.

The engineering contract is state-action tree search: Python owns the tree, Claude proposes actions, Claude or tools simulate next states, scorers rank sibling branches, and the runner returns an auditable path.

The default runner is MCTS-inspired, not naive classic MCTS. Internally, the practical shape is cached state-action beam tree search: expand each selected node once, cache expansions, score children, keep a small beam, and stop early when a verified terminal solution appears. Classic UCT-style repeated visits are only appropriate when branch generation is cheap, stochastic, cached, and backed by a reliable value signal.

The public surface is intentionally small:

1. Claude Code skill: `/reasontree <task>`
2. CLI runner: `reasontree --task "<task>"`

The Python runner is the workflow.

## How It Works

The ReasonTree runner owns the tree:

1. Take the user task.
2. Split context into facts, assumptions/beliefs, user preferences, uncertainties, and hard constraints.
3. Ask for 3-5 candidate actions for the selected state.
4. Convert each action into a child node with facts used, assumptions used, beliefs tested, and node notes.
5. Simulate each action into a next state.
6. Score sibling next states with a verifier or rubric.
7. Keep the best frontier with a small beam.
8. Expand until the depth or node budget is reached.
9. If all branches fail, write a failure note and use it to guide one retry when budget remains.
10. Ask Claude for a critic pass.
11. Return the best first action, selected path, runner-up, tree synthesis, and failure notes.

Claude Code print mode is used internally by the runner. Users do not need to call `claude -p` directly. They need Claude Code installed and authenticated with their own Claude subscription.

For tasks with a reliable external verifier, ReasonTree should use that verifier as the scorer instead of asking Claude to judge every branch narratively. The chess demo uses `scripts/chess_mate_search.py` to verify the selected mate line; code repair can use tests the same way.

Parallelism belongs around independent work: branch scoring, isolated code-path inspection, separate data checks, or independent hypothesis review. The safer default is one proposer call that returns a few diverse branches, one batch scorer that compares siblings, and optional independent rescoring only when the top branches are close. Do not ask multiple agents the identical prompt unless a scorer will compare their outputs.

The final answer should synthesize across the tree, not just return the best leaf. It should identify the facts that mattered, the assumptions that changed branch ranking, the beliefs tested by the tree, and what recommendation remains robust if a key assumption changes.

## Why Python

Python makes the project easier to understand and reuse:

- The search loop is explicit.
- Depth, branch width, beam width, node caps, model, and effort are normal CLI flags.
- Outputs can be saved as JSON for evals.
- It works for chess, code repair, planning, research synthesis, and other tasks.
- It does not require users to learn an additional orchestration runtime.

## Defaults

- `max_depth`: 3
- `branch_width`: 3
- `beam_width`: 2
- `max_nodes`: 48
- maximum depth: 5
- maximum branch width: 5

See also:

- [LLM MCTS literature notes](llm_mcts_literature_notes.md)
- [ReasonTree algorithm options](reasontree_algorithm_options.md)
- [ReasonTree use cases](reasontree_use_cases.md)
- [ReasonTree design brainstorm](reasontree_design_brainstorm.md)

## Safety

The runner disables Claude tools by default. It only asks Claude for structured reasoning JSON. If a task needs local file access or tests, the user can opt in with `--tools default`.

The public chess showcase uses tools deliberately: `/reasontree` runs in a trusted checkout, calls the repo-local chess verifier, and returns the verified first move and principal variation. Pure text `/reasontree` runs are tracked separately as timeout evidence, so the project does not claim that a prompt alone solved the puzzle.
