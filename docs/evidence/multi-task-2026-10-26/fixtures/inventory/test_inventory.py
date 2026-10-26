import unittest

from inventory import summary


class SummaryTests(unittest.TestCase):
    def test_counts_and_totals(self):
        self.assertEqual(summary([("pen", 2, 1.5), ("cup", 1, 4.0)]), (2, 7.0))


if __name__ == "__main__":
    unittest.main()
