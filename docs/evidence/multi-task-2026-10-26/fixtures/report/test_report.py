import unittest

from report import duplicates


class DuplicatesTests(unittest.TestCase):
    def test_lists_each_duplicate_once(self):
        self.assertEqual(duplicates(["a", "b", "a", "a"]), ["a"])


if __name__ == "__main__":
    unittest.main()
