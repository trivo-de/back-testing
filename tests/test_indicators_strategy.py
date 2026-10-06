from decimal import Decimal
import unittest

from backtesting_api.domain.indicators import highest, lowest, sma

D = Decimal


class IndicatorsTest(unittest.TestCase):
    def test_independent_windows_validation_and_unread_future(self):
        series = [D(1), D(3), D(5), D("NaN")]
        for formula, expected in ((sma, D(4)), (highest, D(5)), (lowest, D(3))):
            with self.subTest(formula=formula.__name__):
                self.assertEqual(formula(series, 2, 3), expected)
                self.assertIsNone(formula(series, 4, 3))
                self.assertIsNone(formula([], 1, 0))
                for window in (0, -1, True, 1.5):
                    with self.assertRaisesRegex(ValueError, "window"):
                        formula(series, window, 0)
                for end in (-1, 5, True, 1.5):
                    with self.assertRaisesRegex(ValueError, "end_exclusive"):
                        formula(series, 1, end)
                for invalid in ("NaN", "Infinity", "not-a-number", None):
                    with self.assertRaisesRegex(ValueError, "finite"):
                        formula([invalid], 2, 1)  # Invalid data is not warm-up.
        self.assertEqual(sma([1, 3, 99], 2, 2), D(2))
        self.assertEqual(sma([1, 3, 99], 2, 3), D(51))


if __name__ == "__main__":
    unittest.main()
