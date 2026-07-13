import unittest

from reasontree.verifiers import dependence_bounds


class DependenceBoundsTest(unittest.TestCase):
    def test_correlated_alert_example_is_not_identifiable(self):
        result = dependence_bounds(0.01, 0.9, 0.9, 0.05, 0.05)

        self.assertFalse(result["identifiable"])
        self.assertAlmostEqual(result["posterior_bounds"]["minimum"], 0.1391304347826087)
        self.assertEqual(result["posterior_bounds"]["maximum"], 1.0)
        self.assertAlmostEqual(result["independence_scenario"], 0.7659574468085106)


if __name__ == "__main__":
    unittest.main()
