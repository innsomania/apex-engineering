import unittest

from invoice import render, total


class InvoiceTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([("pen", 2), ("cup", 1)]), 700)

    def test_render(self):
        self.assertEqual(render([("lamp", 1)]), "TOTAL 10.25")


if __name__ == "__main__":
    unittest.main()
