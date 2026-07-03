import unittest
import importlib
import os

module = importlib.import_module(os.environ.get("SEMVER_MODULE", "buggy_semver"))
sort_versions = module.sort_versions


class SemVerSortTest(unittest.TestCase):
    def test_numeric_prerelease_identifiers_sort_numerically(self):
        versions = ["1.0.0-alpha.10", "1.0.0-alpha.2", "1.0.0-alpha.1"]
        self.assertEqual(
            sort_versions(versions),
            ["1.0.0-alpha.1", "1.0.0-alpha.2", "1.0.0-alpha.10"],
        )

    def test_release_sorts_after_prerelease(self):
        versions = ["1.0.0", "1.0.0-rc.1", "1.0.0-beta", "1.0.0-alpha"]
        self.assertEqual(
            sort_versions(versions),
            ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc.1", "1.0.0"],
        )

    def test_shorter_equal_prefix_prerelease_is_lower(self):
        versions = ["1.0.0-alpha.1", "1.0.0-alpha"]
        self.assertEqual(sort_versions(versions), ["1.0.0-alpha", "1.0.0-alpha.1"])

    def test_build_metadata_is_ignored_and_sort_is_stable(self):
        versions = ["1.0.0+build.2", "1.0.0-alpha+build.9", "1.0.0+build.1"]
        self.assertEqual(
            sort_versions(versions),
            ["1.0.0-alpha+build.9", "1.0.0+build.2", "1.0.0+build.1"],
        )


if __name__ == "__main__":
    unittest.main()
