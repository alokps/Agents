from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple, Union
from uuid import uuid4
from collections import defaultdict
import re


Number = Union[int, float, str, Decimal]


class AccountError(Exception):
    """Base exception for all account-related errors."""


class InsufficientFundsError(AccountError):
    """Raised when an operation would result in a negative cash balance."""


class InsufficientHoldingsError(AccountError):
    """Raised when attempting to sell more shares than currently held."""


class InvalidQuantityError(AccountError):
    """Raised when quantity/amount is non-positive or otherwise invalid."""


class InvalidSymbolError(AccountError):
    """Raised when a symbol is empty/invalid or a price cannot be obtained."""


def get_share_price(symbol: str) -> float:
    """
    Test implementation returning fixed prices.
    AAPL -> 180.00
    TSLA -> 250.00
    GOOGL -> 140.00
    """
    if symbol is None:
        raise InvalidSymbolError("Symbol cannot be None.")
    sym = str(symbol).strip().upper()
    prices = {"AAPL": 180.00, "TSLA": 250.00, "GOOGL": 140.00}
    if sym not in prices:
        raise InvalidSymbolError(f"Unknown symbol: {sym!r}")
    return float(prices[sym])


class TransactionType(Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class Transaction:
    id: str
    timestamp: datetime
    type: TransactionType
    symbol: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    note: Optional[str] = None


class Account:
    """
    Simple account management system for a trading simulation platform.

    All transactions are append-only; reporting for "as of" time is done by replaying
    transactions up to the timestamp.
    """

    _SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]*$")

    def __init__(
        self,
        user_id: str,
        *,
        account_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        if user_id is None or str(user_id).strip() == "":
            raise ValueError("user_id must be a non-empty string.")
        self._user_id: str = str(user_id)
        self._account_id: str = account_id if account_id is not None else str(uuid4())
        self._created_at: datetime = self._ensure_utc(created_at) if created_at else self._now_utc()
        self._transactions: List[Transaction] = []

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def deposit(self, amount: Number, *, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> Transaction:
        ts = self._ensure_utc(timestamp) if timestamp else self._now_utc()
        amt = self._to_decimal(amount)
        self._validate_positive_amount(amt, what="deposit amount")
        amt = self._quantize_money(amt)

        tx = Transaction(
            id=str(uuid4()),
            timestamp=ts,
            type=TransactionType.DEPOSIT,
            amount=amt,
            note=note,
        )
        self._append_transaction(tx)
        return tx

    def withdraw(self, amount: Number, *, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> Transaction:
        ts = self._ensure_utc(timestamp) if timestamp else self._now_utc()
        amt = self._to_decimal(amount)
        self._validate_positive_amount(amt, what="withdraw amount")
        amt = self._quantize_money(amt)

        cash = self.cash_balance(as_of=ts)
        if cash < amt:
            raise InsufficientFundsError(f"Insufficient cash for withdrawal. Cash={cash}, requested={amt}")

        tx = Transaction(
            id=str(uuid4()),
            timestamp=ts,
            type=TransactionType.WITHDRAW,
            amount=amt,
            note=note,
        )
        self._append_transaction(tx)
        return tx

    def buy(
        self,
        symbol: str,
        quantity: Number,
        *,
        timestamp: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        ts = self._ensure_utc(timestamp) if timestamp else self._now_utc()
        sym = self._normalize_symbol(symbol)
        qty = self._to_decimal(quantity)
        self._validate_positive_quantity(qty)
        qty = self._quantize_quantity(qty)

        price = self._get_price_decimal(sym)
        cost = self._quantize_money(price * qty)

        cash = self.cash_balance(as_of=ts)
        if cash < cost:
            raise InsufficientFundsError(f"Insufficient cash to buy {qty} {sym}. Cash={cash}, cost={cost}")

        tx = Transaction(
            id=str(uuid4()),
            timestamp=ts,
            type=TransactionType.BUY,
            symbol=sym,
            quantity=qty,
            price=price,
            amount=cost,
            note=note,
        )
        self._append_transaction(tx)
        return tx

    def sell(
        self,
        symbol: str,
        quantity: Number,
        *,
        timestamp: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        ts = self._ensure_utc(timestamp) if timestamp else self._now_utc()
        sym = self._normalize_symbol(symbol)
        qty = self._to_decimal(quantity)
        self._validate_positive_quantity(qty)
        qty = self._quantize_quantity(qty)

        held = self.holdings(as_of=ts).get(sym, Decimal("0"))
        if held < qty:
            raise InsufficientHoldingsError(f"Insufficient holdings to sell. Held={held} {sym}, requested={qty}")

        price = self._get_price_decimal(sym)
        proceeds = self._quantize_money(price * qty)

        tx = Transaction(
            id=str(uuid4()),
            timestamp=ts,
            type=TransactionType.SELL,
            symbol=sym,
            quantity=qty,
            price=price,
            amount=proceeds,
            note=note,
        )
        self._append_transaction(tx)
        return tx

    def transactions(self, *, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[Transaction]:
        s = self._ensure_utc(start) if start else None
        e = self._ensure_utc(end) if end else None

        result: List[Transaction] = []
        for tx in self._transactions:
            if s is not None and tx.timestamp < s:
                continue
            if e is not None and tx.timestamp > e:
                continue
            result.append(tx)
        return list(result)

    def cash_balance(self, *, as_of: Optional[datetime] = None) -> Decimal:
        cash, _pos = self._replay(as_of=as_of)
        return self._quantize_money(cash)

    def holdings(self, *, as_of: Optional[datetime] = None) -> Dict[str, Decimal]:
        _cash, pos = self._replay(as_of=as_of)
        out: Dict[str, Decimal] = {}
        for sym, qty in pos.items():
            q = self._quantize_quantity(qty)
            if q != 0:
                out[sym] = q
        return out

    def portfolio_value(self, *, as_of: Optional[datetime] = None) -> Decimal:
        holdings = self.holdings(as_of=as_of)
        total = Decimal("0")
        for sym, qty in holdings.items():
            price = self._get_price_decimal(sym)
            total += price * qty
        return self._quantize_money(total)

    def equity_value(self, *, as_of: Optional[datetime] = None) -> Decimal:
        return self._quantize_money(self.cash_balance(as_of=as_of) + self.portfolio_value(as_of=as_of))

    def net_contributions(self, *, as_of: Optional[datetime] = None) -> Decimal:
        ts = self._ensure_utc(as_of) if as_of else None
        total = Decimal("0")
        for tx in self._iter_tx_up_to(ts):
            if tx.type == TransactionType.DEPOSIT:
                total += (tx.amount or Decimal("0"))
            elif tx.type == TransactionType.WITHDRAW:
                total -= (tx.amount or Decimal("0"))
        return self._quantize_money(total)

    def profit_loss(self, *, as_of: Optional[datetime] = None) -> Decimal:
        eq = self.equity_value(as_of=as_of)
        contrib = self.net_contributions(as_of=as_of)
        return self._quantize_money(eq - contrib)

    def profit_loss_pct(self, *, as_of: Optional[datetime] = None) -> Optional[Decimal]:
        contrib = self.net_contributions(as_of=as_of)
        if contrib == 0:
            return None
        pl = self.profit_loss(as_of=as_of)
        pct = (pl / contrib) * Decimal("100")
        return pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # -----------------------
    # Internal helpers
    # -----------------------

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ensure_utc(self, dt: datetime) -> datetime:
        if dt is None:
            return self._now_utc()
        if not isinstance(dt, datetime):
            raise TypeError("timestamp must be a datetime.")
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware (UTC recommended).")
        return dt.astimezone(timezone.utc)

    def _to_decimal(self, value: Number) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            # Use str() to reduce float binary artifacts
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidQuantityError(f"Invalid numeric value: {value!r}") from e

    def _quantize_money(self, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _quantize_quantity(self, qty: Decimal) -> Decimal:
        # Support fractional shares with up to 8 decimal places by default.
        return qty.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    def _normalize_symbol(self, symbol: str) -> str:
        if symbol is None:
            raise InvalidSymbolError("Symbol cannot be None.")
        sym = str(symbol).strip().upper()
        if sym == "":
            raise InvalidSymbolError("Symbol cannot be empty.")
        if not self._SYMBOL_RE.match(sym):
            raise InvalidSymbolError(f"Invalid symbol format: {sym!r}")
        # Validate it can be priced (at least for this test price function)
        _ = self._get_price_decimal(sym)
        return sym

    def _get_price_decimal(self, symbol: str) -> Decimal:
        try:
            p = get_share_price(symbol)
        except InvalidSymbolError:
            raise
        except Exception as e:
            raise InvalidSymbolError(f"Failed to get price for symbol {symbol!r}: {e}") from e
        try:
            price = Decimal(str(p))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidSymbolError(f"Invalid price returned for symbol {symbol!r}: {p!r}") from e
        if price <= 0:
            raise InvalidSymbolError(f"Non-positive price for symbol {symbol!r}: {price}")
        return self._quantize_money(price)

    def _validate_positive_quantity(self, quantity: Decimal) -> None:
        if quantity is None:
            raise InvalidQuantityError("Quantity cannot be None.")
        if quantity <= 0:
            raise InvalidQuantityError(f"Quantity must be > 0. Got: {quantity}")

    def _validate_positive_amount(self, amount: Decimal, *, what: str = "amount") -> None:
        if amount is None:
            raise InvalidQuantityError(f"{what} cannot be None.")
        if amount <= 0:
            raise InvalidQuantityError(f"{what} must be > 0. Got: {amount}")

    def _iter_tx_up_to(self, as_of: Optional[datetime]) -> Iterable[Transaction]:
        if as_of is None:
            yield from self._transactions
            return
        for tx in self._transactions:
            if tx.timestamp <= as_of:
                yield tx

    def _append_transaction(self, tx: Transaction) -> None:
        # Keep chronological order; if backdated timestamps are used, insert and keep stable.
        if not self._transactions or self._transactions[-1].timestamp <= tx.timestamp:
            self._transactions.append(tx)
            return
        # Insert for backdated tx
        lo, hi = 0, len(self._transactions)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._transactions[mid].timestamp <= tx.timestamp:
                lo = mid + 1
            else:
                hi = mid
        self._transactions.insert(lo, tx)

    def _replay(self, *, as_of: Optional[datetime] = None) -> Tuple[Decimal, Dict[str, Decimal]]:
        ts = self._ensure_utc(as_of) if as_of else None
        cash = Decimal("0")
        pos: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for tx in self._iter_tx_up_to(ts):
            t = tx.type
            if t == TransactionType.DEPOSIT:
                cash += (tx.amount or Decimal("0"))
            elif t == TransactionType.WITHDRAW:
                cash -= (tx.amount or Decimal("0"))
            elif t == TransactionType.BUY:
                if tx.symbol is None or tx.quantity is None or tx.price is None:
                    raise AccountError(f"Corrupt BUY transaction: {tx}")
                cash -= tx.price * tx.quantity
                pos[tx.symbol] += tx.quantity
            elif t == TransactionType.SELL:
                if tx.symbol is None or tx.quantity is None or tx.price is None:
                    raise AccountError(f"Corrupt SELL transaction: {tx}")
                cash += tx.price * tx.quantity
                pos[tx.symbol] -= tx.quantity
            else:
                raise AccountError(f"Unknown transaction type: {t}")

        # Normalize to Decimals with expected precision (but do not drop symbols here)
        cash = self._quantize_money(cash)
        for sym in list(pos.keys()):
            pos[sym] = self._quantize_quantity(pos[sym])

        return cash, dict(pos)