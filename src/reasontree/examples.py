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


def get_adapter(name: str):
    adapters = {
        "chess": ChessMateAdapter,
    }
    if name not in adapters:
        raise ValueError(f"Unknown demo {name!r}. Use one of: {', '.join(adapters)}")
    return adapters[name]()
