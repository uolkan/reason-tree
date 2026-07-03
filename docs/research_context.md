# Research Context

Last updated: 2026-07-01.

## Current Frontier-Model Context

OpenAI's GPT-5.6 Sol preview is explicitly framed as a staged release. OpenAI says the preview starts with trusted partners whose participation has been shared with the U.S. government, before broader release. The launch also introduces `max` reasoning effort and an `ultra` mode that goes beyond one agent by using subagents for complex work.

Anthropic's Claude Code skills and agentic workflows make a similar product pattern visible: difficult tasks are increasingly decomposed into tools, role prompts, and multi-step control loops instead of one model call.

The broader product pattern is that frontier-model access, reasoning effort, and agentic orchestration are becoming tiered capabilities. That makes search-time workflow design relevant for two reasons:

- Access: most users and developers will not always have the strongest model.
- Reliability: users still need practical ways to structure hard problems with the models and subscriptions they actually have.

ReasonTree sits in the middle: it is a small open-source workflow pattern for improving reliability with the models people can actually access.

## Link to the Local MCTS Archive

The local archive contains several generations of LLM-guided MCTS experiments:

- early GPT-3.5/GPT-4 reasoning-tree prototypes
- action proposal, next-state simulation, reward scoring, bounded frontier selection, and optional value backpropagation when full MCTS is explicitly enabled
- JSON-structured prompt contracts
- failure cases around non-numeric reward parsing and API instability
- chess-puzzle preparation over 549,653 Lichess puzzle rows
- puzzle prompt/notation/label generation from FEN and PGN fields

Relevant local source digests:

- `/Users/volkan/Desktop/research/TRADE_EXPERIMENTS_ARCHIVE/LATEST_NOTEBOOKS_MAC/_digests/MCTS/Reason with MCTS-good backup.ipynb.md`
- `/Users/volkan/Desktop/research/TRADE_EXPERIMENTS_ARCHIVE/LATEST_NOTEBOOKS_MAC/_digests/MCTS/Reason with MCTS-v5-working_backup.ipynb.md`
- `/Users/volkan/Desktop/research/TRADE_EXPERIMENTS_ARCHIVE/LATEST_NOTEBOOKS_MAC/_digests/MCTS/Puzzle Preparation New MCTS.ipynb.md`
- `/Users/volkan/Desktop/research/TRADE_EXPERIMENTS_ARCHIVE/LATEST_NOTEBOOKS_MAC/_digests/MCTS/knowledge-Copy2.ipynb.md`

## Defensible Project Framing

The strongest public framing is:

> Search-time reasoning workflows can make model behavior more reliable on brittle tasks by externalizing the plan into an auditable tree: propose branches, simulate consequences, score them, and choose the best path.

This is close to Tree of Thoughts, Reasoning via Planning, self-consistency, best-of-N, verifier-guided decoding, and multi-agent critique. The differentiator for this repo is the practical packaging: a small reusable skill, a Python ReasonTree runner, visual traces, and an evaluation harness.

## Sources

- OpenAI: https://openai.com/index/previewing-gpt-5-6-sol/
- OpenAI GPT-5.6 Help Center: https://help.openai.com/en/articles/20001325-a-preview-of-gpt-56-sol-terra-and-luna
- OpenAI GPT-5.6 preview system card: https://deploymentsafety.openai.com/gpt-5-6-preview
- Anthropic Claude Code skills: https://code.claude.com/docs/en/skills
- Anthropic Claude Code subagents: https://code.claude.com/docs/en/sub-agents
