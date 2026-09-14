from decimal import Decimal
import unittest

from backtest_hpg.application.result_mapper import quantize_result, serialize_result


class PrecisionTest(unittest.TestCase):
    def test_result_boundary_uses_six_decimal_half_up(self):
        value = {"up": Decimal("1.2345675"), "down": [Decimal("1.2345674")]}
        self.assertEqual(
            quantize_result(value),
            {"up": Decimal("1.234568"), "down": [Decimal("1.234567")]},
        )
        self.assertEqual(serialize_result(value), {"up": "1.234568", "down": ["1.234567"]})


if __name__ == "__main__":
    unittest.main()
