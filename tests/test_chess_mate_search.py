import unittest

from scripts.chess_mate_search import solve


class ChessMateSearchTest(unittest.TestCase):
    def test_medium_mate_in_two_solution(self):
        result = solve("4r3/2Q5/p3qkp1/1p1p2pp/2bP4/P3B1PP/1RP1PPK1/6N1 w - - 0 1", 2)
        moves = {item["move"] for item in result["solutions"]}
        self.assertIn("Bxg5+", moves)


if __name__ == "__main__":
    unittest.main()
