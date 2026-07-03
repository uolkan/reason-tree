from __future__ import annotations

from .core import Branch


class ChessMateAdapter:
    name = "chess_mate2"
    label = "Bxg5+"
    root_state = "White to move: 4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1"

    def direct_baseline(self) -> str:
        return "direct run did not complete under eval budget"

    def branches(self, state: str) -> list[Branch]:
        tree = {
            self.root_state: [
                Branch("Qf7+?", "1. Qf7+?", -0.7, "Looks natural, but the queen is exposed and it is not a forced mate.", True),
                Branch("Bxg5+", "1. Bxg5+", 0.65, "Sacrifices the bishop to force the black king onto g5 or f5."),
                Branch("Qh7?", "1. Qh7?", -0.5, "Creates pressure but does not force mate in two.", True),
            ],
            "1. Bxg5+": [
                Branch("...Kxg5", "1. Bxg5+ Kxg5", 0.95, "The king capture walks into Qf4 mate."),
                Branch("...Kf5", "1. Bxg5+ Kf5", 0.9, "The king move is also met by Qf4 mate."),
                Branch("...hxg5?", "1. Bxg5+ hxg5?", 0.2, "Not the principal legal defense from the FEN.", True),
            ],
            "1. Bxg5+ Kxg5": [
                Branch("Qf4#", "1. Bxg5+ Kxg5 2. Qf4#", 1.0, "The queen covers the escape squares and gives mate.", True),
                Branch("Nf3+?", "1. Bxg5+ Kxg5 2. Nf3+?", -0.4, "A check but not mate.", True),
            ],
            "1. Bxg5+ Kf5": [
                Branch("Qf4#", "1. Bxg5+ Kf5 2. Qf4#", 1.0, "The same queen move mates after the king steps to f5.", True),
                Branch("Nf3+?", "1. Bxg5+ Kf5 2. Nf3+?", -0.4, "A check but not mate.", True),
            ],
        }
        return tree.get(state, [])


class PlanningAdapter:
    name = "planning_context_ledger"
    label = "launch_pilot_with_rollback_and_review"
    root_state = (
        "Decision: ship a customer-facing change by Friday or wait for a broader refactor. "
        "Facts: customer impact is high, rollback is easy, refactor risk is medium, deadline is Friday. "
        "Belief: asking for a narrower pilot may look weak. Preference: choose a low-regret reversible move."
    )

    def direct_baseline(self) -> str:
        return "ship the full change now"

    def branches(self, state: str) -> list[Branch]:
        tree = {
            self.root_state: [
                Branch(
                    "ship_full_change_now",
                    "State S1: full launch happens before the refactor is ready",
                    0.25,
                    "Fast, but it assumes urgency matters more than reversibility and risk control.",
                    True,
                    facts_used=("customer impact is high", "deadline is Friday"),
                    assumptions_used=("speed matters more than reversibility",),
                    beliefs_tested=("the boldest visible action is the best action",),
                    node_notes=("This branch optimizes momentum but has weak downside control.",),
                ),
                Branch(
                    "run_reversible_pilot",
                    "State S2: a smaller launch creates evidence while preserving rollback",
                    0.72,
                    "Balances customer urgency with a reversible path and gives the team information.",
                    facts_used=("customer impact is high", "rollback is easy", "deadline is Friday"),
                    assumptions_used=("a smaller pilot can still create visible customer value",),
                    beliefs_tested=("asking for a narrower pilot looks weak",),
                    node_notes=("This branch converts the psychological belief into a testable communication problem.",),
                ),
                Branch(
                    "delay_for_refactor",
                    "State S3: release waits for the broader refactor",
                    0.38,
                    "Reduces implementation risk but under-serves the high customer impact before Friday.",
                    True,
                    facts_used=("refactor risk is medium", "customer impact is high"),
                    assumptions_used=("waiting will materially improve the release quality",),
                    beliefs_tested=("perfecting the implementation beats learning from a small release",),
                    node_notes=("This branch is safer technically but weak on time-to-learn.",),
                ),
            ],
            "State S2: a smaller launch creates evidence while preserving rollback": [
                Branch(
                    "define_pilot_success_metric",
                    "State S2a: success criteria are explicit before launch",
                    0.78,
                    "Clarifies what evidence the pilot must create, but does not itself deliver value yet.",
                    facts_used=("customer impact is high",),
                    assumptions_used=("the team can agree on a success metric quickly",),
                    beliefs_tested=("a smaller launch is only useful if learning is explicit",),
                    node_notes=("Good support action, but it should be paired with an actual pilot.",),
                ),
                Branch(
                    "pilot_to_small_segment",
                    "State S2b: a limited segment gets the change with rollback ready",
                    0.9,
                    "Creates customer value, preserves reversibility, and tests whether the weak-looking pilot belief is real.",
                    facts_used=("rollback is easy", "deadline is Friday", "customer impact is high"),
                    assumptions_used=("a limited segment is enough to learn",),
                    beliefs_tested=("a staged plan looks weak to stakeholders",),
                    node_notes=("This branch dominates because it is action plus learning, not delay disguised as safety.",),
                ),
                Branch(
                    "ask_for_full_delay",
                    "State S2c: stakeholders are asked to wait for the refactor",
                    0.45,
                    "May be defensible, but it avoids the reversible option already available.",
                    True,
                    facts_used=("refactor risk is medium",),
                    assumptions_used=("stakeholders will accept delay without near-term value",),
                    beliefs_tested=("delay is safer than a bounded experiment",),
                    node_notes=("This branch should be kept as a fallback, not the default.",),
                ),
            ],
            "State S2b: a limited segment gets the change with rollback ready": [
                Branch(
                    "launch_pilot_with_rollback_and_review",
                    "State S2b1: pilot launches, rollback is ready, review is scheduled",
                    0.96,
                    "This keeps the deadline, reduces regret, and makes the belief about looking weak observable.",
                    True,
                    facts_used=("rollback is easy", "deadline is Friday", "customer impact is high"),
                    assumptions_used=("reviewing pilot evidence is acceptable to stakeholders",),
                    beliefs_tested=("visible progress plus evidence is stronger than full launch theater",),
                    node_notes=("Recommended first move: pilot now, review evidence, then decide whether to widen.",),
                ),
                Branch(
                    "launch_pilot_without_review",
                    "State S2b2: pilot launches but no review cadence exists",
                    0.55,
                    "The action is reversible but the learning loop is weak.",
                    True,
                    facts_used=("rollback is easy",),
                    assumptions_used=("the pilot will naturally create usable feedback",),
                    beliefs_tested=("action without review is enough",),
                    node_notes=("This loses the main value of the state-action tree: explicit learning.",),
                ),
            ],
        }
        return tree.get(state, [])


def get_adapter(name: str):
    adapters = {
        "chess": ChessMateAdapter,
        "planning": PlanningAdapter,
    }
    if name not in adapters:
        raise ValueError(f"Unknown demo {name!r}. Use one of: {', '.join(adapters)}")
    return adapters[name]()
