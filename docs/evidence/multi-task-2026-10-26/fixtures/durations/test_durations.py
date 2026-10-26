import unittest

from durations import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_single_unit(self):
        self.assertEqual(parse_duration("45s"), 45)


if __name__ == "__main__":
    unittest.main()
