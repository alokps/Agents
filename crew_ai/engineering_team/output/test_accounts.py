import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import accounts
from accounts import (
    Account,
    AccountError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidQuantityError,
    InvalidSymbolError,
    TransactionType,
)


class TestAccountInitialization(unittest.TestCase):
    def test_init_requires_non_empty_user_id(self):
        with self.assertRaises(ValueError):
            Account("")
        with self.assertRaises(ValueError):
            Account("   ")
        with self.assertRaises(ValueError):
            Account(None)  # type: ignore[arg-type]

    def test_init_sets_account_id_and_created_at_utc(self):
        created = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        acct = Account("u1", account_id="acc-1", created_at=created)
        self.assertEqual(acct.user_id, "u1")
        self.assertEqual(acct.account_id, "acc-1")
        self.assertEqual(acct.created_at, created)
        self.assertIsNotNone(acct.created_at.tzinfo)
        self.assertEqual(acct.created_at.tzinfo, timezone.utc)

    def test_init_created_at_requires_timezone_aware(self):
        naive = datetime(2025, 1, 1, 12, 0, 0)
        with self.assertRaises(ValueError):
            Account("u1", created_at=naive)  # type: ignore[arg-type]

    def test_init_created_at_requires_datetime(self):
        with self.assertRaises(TypeError):
            Account("u1", created_at="2025-01-01")  # type: ignore[arg-type]


class TestMoneyAndQuantityValidation(unittest.TestCase):
    def setUp(self):
        self.acct = Account("u1")

    def test_deposit_quantizes_money_and_records_transaction(self):
        ts = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        tx = self.acct.deposit("10.005", timestamp=ts, note="x")
        self.assertEqual(tx.type, TransactionType.DEPOSIT)
        self.assertEqual(tx.amount, Decimal("10.01"))
        self.assertEqual(tx.timestamp, ts)
        self.assertEqual(tx.note, "x")
        self.assertEqual(self.acct.cash_balance(as_of=ts), Decimal("10.01"))

    def test_withdraw_quantizes_money(self):
        ts = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.acct.deposit("10.00", timestamp=ts)
        tx = self.acct.withdraw("1.005", timestamp=ts + timedelta(seconds=1))
        self.assertEqual(tx.amount, Decimal("1.01"))
        self.assertEqual(self.acct.cash_balance(as_of=ts + timedelta(seconds=1)), Decimal("8.99"))

    def test_deposit_requires_positive_amount(self):
        with self.assertRaises(InvalidQuantityError):
            self.acct.deposit(0)
        with self.assertRaises(InvalidQuantityError):
            self.acct.deposit(-1)
        with self.assertRaises(InvalidQuantityError):
            self.acct.deposit(None)  # type: ignore[arg-type]
        with self.assertRaises(InvalidQuantityError):
            self.acct.deposit("not-a-number")

    def test_withdraw_requires_positive_amount(self):
        self.acct.deposit("10")
        with self.assertRaises(InvalidQuantityError):
            self.acct.withdraw(0)
        with self.assertRaises(InvalidQuantityError):
            self.acct.withdraw(-1)
        with self.assertRaises(InvalidQuantityError):
            self.acct.withdraw(None)  # type: ignore[arg-type]
        with self.assertRaises(InvalidQuantityError):
            self.acct.withdraw("nope")

    def test_withdraw_insufficient_funds_raises(self):
        ts = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.acct.deposit("5.00", timestamp=ts)
        with self.assertRaises(InsufficientFundsError):
            self.acct.withdraw("5.01", timestamp=ts + timedelta(seconds=1))


class TestSymbolsAndPricing(unittest.TestCase):
    def setUp(self):
        self.acct = Account("u1")
        self.base = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_get_share_price_known_symbols(self):
        self.assertEqual(accounts.get_share_price("AAPL"), 180.0)
        self.assertEqual(accounts.get_share_price("tsla"), 250.0)
        self.assertEqual(accounts.get_share_price(" GOOGL "), 140.0)

    def test_get_share_price_unknown_symbol_raises(self):
        with self.assertRaises(InvalidSymbolError):
            accounts.get_share_price("MSFT")

    def test_buy_rejects_invalid_symbols(self):
        self.acct.deposit("1000", timestamp=self.base)
        with self.assertRaises(InvalidSymbolError):
            self.acct.buy("", 1, timestamp=self.base + timedelta(seconds=1))
        with self.assertRaises(InvalidSymbolError):
            self.acct.buy("   ", 1, timestamp=self.base + timedelta(seconds=1))
        with self.assertRaises(InvalidSymbolError):
            self.acct.buy(None, 1, timestamp=self.base + timedelta(seconds=1))  # type: ignore[arg-type]
        with self.assertRaises(InvalidSymbolError):
            self.acct.buy("BAD-SYM", 1, timestamp=self.base + timedelta(seconds=1))
        with self.assertRaises(InvalidSymbolError):
            self.acct.buy("MSFT", 1, timestamp=self.base + timedelta(seconds=1))

    def test_buy_accepts_case_insensitive_and_normalizes(self):
        self.acct.deposit("1000", timestamp=self.base)
        tx = self.acct.buy("aapl", "1", timestamp=self.base + timedelta(seconds=1))
        self.assertEqual(tx.symbol, "AAPL")
        self.assertEqual(tx.price, Decimal("180.00"))
        self.assertEqual(tx.quantity, Decimal("1.00000000"))
        self.assertEqual(tx.amount, Decimal("180.00"))

    def test_buy_quantity_validation_and_quantization(self):
        self.acct.deposit("1000", timestamp=self.base)
        with self.assertRaises(InvalidQuantityError):
            self.acct.buy("AAPL", 0, timestamp=self.base + timedelta(seconds=1))
        with self.assertRaises(InvalidQuantityError):
            self.acct.buy("AAPL", -1, timestamp=self.base + timedelta(seconds=1))
        with self.assertRaises(InvalidQuantityError):
            self.acct.buy("AAPL", None, timestamp=self.base + timedelta(seconds=1))  # type: ignore[arg-type]
        with self.assertRaises(InvalidQuantityError):
            self.acct.buy("AAPL", "not-a-number", timestamp=self.base + timedelta(seconds=1))

        tx = self.acct.buy("AAPL", "1.123456789", timestamp=self.base + timedelta(seconds=2))
        self.assertEqual(tx.quantity, Decimal("1.12345679"))  # 8 dp, half-up

    def test_buy_insufficient_funds_raises(self):
        self.acct.deposit("10.00", timestamp=self.base)
        with self.assertRaises(InsufficientFundsError):
            self.acct.buy("AAPL", 1, timestamp=self.base + timedelta(seconds=1))


class TestTradingAndReporting(unittest.TestCase):
    def setUp(self):
        self.acct = Account("u1")
        self.t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.t1 = self.t0 + timedelta(seconds=1)
        self.t2 = self.t0 + timedelta(seconds=2)
        self.t3 = self.t0 + timedelta(seconds=3)
        self.t4 = self.t0 + timedelta(seconds=4)
        self.t5 = self.t0 + timedelta(seconds=5)

    def test_holdings_cash_portfolio_equity_profit_loss(self):
        self.acct.deposit("1000.00", timestamp=self.t0)

        buy = self.acct.buy("AAPL", "2", timestamp=self.t1)
        self.assertEqual(buy.amount, Decimal("360.00"))
        self.assertEqual(self.acct.cash_balance(as_of=self.t1), Decimal("640.00"))
        self.assertEqual(self.acct.holdings(as_of=self.t1), {"AAPL": Decimal("2.00000000")})
        self.assertEqual(self.acct.portfolio_value(as_of=self.t1), Decimal("360.00"))
        self.assertEqual(self.acct.equity_value(as_of=self.t1), Decimal("1000.00"))
        self.assertEqual(self.acct.net_contributions(as_of=self.t1), Decimal("1000.00"))
        self.assertEqual(self.acct.profit_loss(as_of=self.t1), Decimal("0.00"))
        self.assertEqual(self.acct.profit_loss_pct(as_of=self.t1), Decimal("0.00"))

        sell = self.acct.sell("AAPL", "1", timestamp=self.t2)
        self.assertEqual(sell.amount, Decimal("180.00"))
        self.assertEqual(self.acct.cash_balance(as_of=self.t2), Decimal("820.00"))
        self.assertEqual(self.acct.holdings(as_of=self.t2), {"AAPL": Decimal("1.00000000")})
        self.assertEqual(self.acct.portfolio_value(as_of=self.t2), Decimal("180.00"))
        self.assertEqual(self.acct.equity_value(as_of=self.t2), Decimal("1000.00"))
        self.assertEqual(self.acct.profit_loss(as_of=self.t2), Decimal("0.00"))

        self.acct.withdraw("200.00", timestamp=self.t3)
        self.assertEqual(self.acct.cash_balance(as_of=self.t3), Decimal("620.00"))
        self.assertEqual(self.acct.net_contributions(as_of=self.t3), Decimal("800.00"))
        self.assertEqual(self.acct.equity_value(as_of=self.t3), Decimal("800.00"))
        self.assertEqual(self.acct.profit_loss(as_of=self.t3), Decimal("0.00"))

        # Edge: profit_loss_pct as_of with zero contributions
        acct2 = Account("u2")
        self.assertIsNone(acct2.profit_loss_pct())

    def test_sell_more_than_holdings_raises(self):
        self.acct.deposit("1000", timestamp=self.t0)
        self.acct.buy("TSLA", "1", timestamp=self.t1)
        with self.assertRaises(InsufficientHoldingsError):
            self.acct.sell("TSLA", "1.00000001", timestamp=self.t2)

    def test_transactions_filter_start_end(self):
        self.acct.deposit("10", timestamp=self.t0, note="d0")
        self.acct.deposit("10", timestamp=self.t1, note="d1")
        self.acct.deposit("10", timestamp=self.t2, note="d2")

        all_txs = self.acct.transactions()
        self.assertEqual([tx.note for tx in all_txs], ["d0", "d1", "d2"])

        start_filtered = self.acct.transactions(start=self.t1)
        self.assertEqual([tx.note for tx in start_filtered], ["d1", "d2"])

        end_filtered = self.acct.transactions(end=self.t1)
        self.assertEqual([tx.note for tx in end_filtered], ["d0", "d1"])

        range_filtered = self.acct.transactions(start=self.t1, end=self.t1)
        self.assertEqual([tx.note for tx in range_filtered], ["d1"])

    def test_as_of_filters_include_equal_timestamps(self):
        self.acct.deposit("100", timestamp=self.t0)
        self.acct.withdraw("10", timestamp=self.t1)
        self.assertEqual(self.acct.cash_balance(as_of=self.t0), Decimal("100.00"))
        self.assertEqual(self.acct.cash_balance(as_of=self.t1), Decimal("90.00"))

    def test_backdated_transaction_insertion_keeps_chronological_replay(self):
        self.acct.deposit("1000", timestamp=self.t0)
        # Add a later buy first
        self.acct.buy("AAPL", "1", timestamp=self.t4)  # cost 180, cash 820 at t4
        # Backdate a deposit between
        self.acct.deposit("100", timestamp=self.t2)

        # As of t3 should include deposit but not buy
        self.assertEqual(self.acct.cash_balance(as_of=self.t3), Decimal("1100.00"))
        self.assertEqual(self.acct.holdings(as_of=self.t3), {})

        # As of t5 includes all
        self.assertEqual(self.acct.cash_balance(as_of=self.t5), Decimal("920.00"))
        self.assertEqual(self.acct.holdings(as_of=self.t5), {"AAPL": Decimal("1.00000000")})

        # Ensure transactions() returns in order by timestamp (stable within same timestamp)
        txs = self.acct.transactions()
        self.assertEqual([tx.timestamp for tx in txs], sorted([tx.timestamp for tx in txs]))
        self.assertEqual([tx.type for tx in txs], [TransactionType.DEPOSIT, TransactionType.DEPOSIT, TransactionType.BUY])

    def test_timezone_handling_for_api_methods(self):
        self.acct.deposit("10", timestamp=self.t0)
        naive = datetime(2025, 1, 1, 10, 0, 0)
        with self.assertRaises(ValueError):
            self.acct.deposit("1", timestamp=naive)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.acct.cash_balance(as_of=naive)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.acct.withdraw("1", timestamp="2025-01-01T00:00:00Z")  # type: ignore[arg-type]


class TestReplayCorruptionAndUnknownType(unittest.TestCase):
    def setUp(self):
        self.acct = Account("u1")
        self.t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_replay_detects_corrupt_buy_transaction(self):
        # Append a corrupt BUY transaction by direct internal access.
        bad_tx = accounts.Transaction(
            id="x",
            timestamp=self.t0,
            type=TransactionType.BUY,
            symbol="AAPL",
            quantity=None,
            price=Decimal("180.00"),
            amount=Decimal("180.00"),
            note=None,
        )
        self.acct._transactions.append(bad_tx)  # type: ignore[attr-defined]
        with self.assertRaises(AccountError):
            self.acct.cash_balance()

    def test_replay_detects_unknown_transaction_type(self):
        class FakeType:
            pass

        bad_tx = accounts.Transaction(
            id="x",
            timestamp=self.t0,
            type=FakeType(),  # type: ignore[arg-type]
            symbol=None,
            quantity=None,
            price=None,
            amount=Decimal("1.00"),
            note=None,
        )
        self.acct._transactions.append(bad_tx)  # type: ignore[attr-defined]
        with self.assertRaises(AccountError):
            self.acct.cash_balance()


if __name__ == "__main__":
    unittest.main()