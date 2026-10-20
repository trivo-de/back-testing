from decimal import Decimal as D
import unittest

from backtesting_api.domain.contract_accounting import ContractAccounting, ContractBook, ContractPortfolio


ACCOUNTING = ContractAccounting('.17', '.001', '2700', '2550', '0')


class ContractBookTest(unittest.TestCase):
    def test_one_lot_matches_existing_ledger(self):
        for side in ('LONG', 'SHORT'):
            with self.subTest(side=side):
                single = ContractPortfolio.open(100000000, ACCOUNTING)
                book = ContractBook.open(100000000, ACCOUNTING)
                single, costs = single.enter(side, 3, D('1000.2'))
                book, book_costs = book.enter('A', side, 3, D('1000.2'))
                self.assertEqual(book_costs, costs)
                self.assertEqual(book.portfolio_for('A'), single)
                self.assertEqual(book.mark(1005), single.mark(1005))
                for quantity, price in ((1, 1006), (2, 1012)):
                    single, *expected = single.exit(quantity, price)
                    book, *actual = book.exit('A', quantity, price)
                    self.assertEqual(actual, expected)
                    self.assertEqual(book.portfolio_for('A'), single)
                    self.assertEqual(book.mark(price), single.mark(price))

    def test_lots_keep_cost_basis_and_close_only_the_named_lot(self):
        for side, sign in (('LONG', 1), ('SHORT', -1)):
            with self.subTest(side=side):
                book = ContractBook.open(200000000, ACCOUNTING)
                book, first_cost = book.enter('A', side, 3, D('1000.2'))
                book, second_cost = book.enter('B', side, 2, D('1002.2'))
                second = book.lot('B')
                self.assertEqual(book.quantity, 5)
                self.assertEqual(book.mark(D('1003.2')).unrealized_pnl, sign * 1100000)
                self.assertEqual(book.mark(D('1003.2')).required_margin, 85272000)
                allocations = []
                for _ in range(3):
                    book, _, allocated, _ = book.exit('A', 1, D('1003.2'))
                    allocations.append(allocated)
                    self.assertEqual(book.lot('B'), second)
                self.assertEqual(allocations, [13752, 13752, 13751])
                self.assertEqual(sum(allocations), first_cost.total)
                self.assertIsNone(book.lot('A'))
                book, _, allocated, _ = book.exit('B', 2, D('1003.2'))
                self.assertEqual(allocated, second_cost.total)
                self.assertEqual(book.positions, ())
                self.assertEqual(book.cash - 200000000, book.realized_pnl)
                self.assertEqual(book.realized_pnl, sign * 1100000 - book.fees)
                self.assertEqual(book.mark(1000).equity, book.cash)

    def test_shared_margin_limit_direction_and_reduce_only(self):
        book = ContractBook.open(30000000, ACCOUNTING)
        book, _ = book.enter('A', 'LONG', 1, 1000)
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_MARGIN_AFTER_COSTS'):
            book.enter('B', 'LONG', 1, 1000)
        with self.assertRaisesRegex(ValueError, 'OPPOSITE_POSITION_EXISTS'):
            book.enter('B', 'SHORT', 1, 1000)
        with self.assertRaisesRegex(ValueError, 'MAX_CONTRACTS_EXCEEDED'):
            book.enter('B', 'LONG', 1, 1000, max_contracts=1)
        for position_id, quantity in (('missing', 1), ('A', 2), ('A', True)):
            with self.assertRaises(ValueError):
                book.exit(position_id, quantity, 1000)
        for position_id in ('A', '', None):
            with self.assertRaisesRegex(ValueError, 'INVALID_POSITION_ID'):
                book.enter(position_id, 'LONG', 1, 1000)
        self.assertEqual(book.quantity, 1)
        self.assertEqual(book.lot('A').entry_price, 1000)


if __name__ == '__main__':
    unittest.main()
