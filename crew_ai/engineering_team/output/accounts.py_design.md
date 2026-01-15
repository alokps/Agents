```markdown
# accounts.py — Detailed Design (Single-Module, Self-Contained)

## Goals
Implement a simple account management system for a trading simulation platform in a single Python module named **`accounts.py`** containing a primary class **`Account`**. The module must support:

- Account creation
- Deposits and withdrawals (no negative cash balance allowed)
- Buying and selling shares (cannot buy beyond available cash; cannot sell beyond holdings)
- Transaction history over time
- Holdings reporting “at any point in time”
- Profit/Loss reporting “at any point in time”
- Portfolio valuation using `get_share_price(symbol)` (current price function; include test implementation with fixed prices for AAPL/TSLA/GOOGL)

This design is intended to be directly implementable and testable, and suitable for a simple UI layer.

---

## Module Structure Overview

### Public API (what a UI/test would primarily use)
- `class Account`
  - `__init__(...)`
  - `deposit(...)`
  - `withdraw(...)`
  - `buy(...)`
  - `sell(...)`
  - `cash_balance(as_of=None)`
  - `holdings(as_of=None)`
  - `transactions(start=None, end=None)`
  - `portfolio_value(as_of=None)`
  - `equity_value(as_of=None)`
  - `profit_loss(as_of=None)`
  - `profit_loss_pct(as_of=None)`

### Supporting Components (in the same module)
- `get_share_price(symbol: str) -> float` (test implementation included)
- Data models:
  - `TransactionType` (Enum)
  - `Transaction` (dataclass)
- Exceptions:
  - `AccountError` (base)
  - `InsufficientFundsError`
  - `InsufficientHoldingsError`
  - `InvalidQuantityError`
  - `InvalidSymbolError`

---

## Data Model & Concepts

### Time Handling
- Each transaction is timestamped using timezone-aware UTC `datetime`.
- “At any point in time” is supported by replaying transactions up to a given timestamp (`as_of`).

### Money & Precision
- Use `decimal.Decimal` for monetary values to avoid floating point errors.
- Share quantities are best represented as `Decimal` too (allows fractional shares if desired). If fractional shares are not desired, enforce integer quantities at validation—this design supports either by configuration or by validation policy (choose one in implementation).

### Valuation Rules
- **Cash Balance**: derived from deposits/withdrawals and trade cash flows.
- **Holdings**: share quantities by symbol derived from buy/sell transactions.
- **Portfolio Value**: sum over holdings `qty * current_price(symbol)` (or price at time if implemented later; requirement only specifies current price function).
- **Equity Value**: `cash_balance + portfolio_value`.
- **Initial Deposit**: net deposited cash baseline for P/L:
  - Interpret “initial deposit” as the **net cash funded by the user**: `total_deposits - total_withdrawals` up to that time.
  - Profit/Loss at time `t`: `equity_value(t) - net_contributions(t)`.
    - This makes P/L meaningful even if user adds/withdraws funds later.
  - If you want strict “first deposit only”, you can store the first deposit amount; but given real behaviors, net contributions is typically correct and stable.

---

## Exceptions

### `class AccountError(Exception)`
Base exception for all account issues.

### `class InsufficientFundsError(AccountError)`
Raised when a withdrawal or buy would result in negative cash balance.

### `class InsufficientHoldingsError(AccountError)`
Raised when a sell quantity exceeds currently held shares.

### `class InvalidQuantityError(AccountError)`
Raised when quantity is non-positive or invalid for the system.

### `class InvalidSymbolError(AccountError)`
Raised when symbol is empty or invalid format, or price lookup fails.

---

## Enumerations & Dataclasses

### `class TransactionType(enum.Enum)`
Represents transaction categories.

**Members**
- `DEPOSIT`
- `WITHDRAW`
- `BUY`
- `SELL`

### `@dataclass(frozen=True) class Transaction`
Immutable record of a single account event.

**Fields**
- `id: str`
  - Unique transaction id (e.g., UUID4 string).
- `timestamp: datetime`
  - Time the transaction occurred (UTC aware).
- `type: TransactionType`
- `symbol: str | None`
  - For BUY/SELL; None for DEPOSIT/WITHDRAW.
- `quantity: Decimal | None`
  - For BUY/SELL; None for DEPOSIT/WITHDRAW.
- `price: Decimal | None`
  - For BUY/SELL; stored execution price at the time of trade.
  - For DEPOSIT/WITHDRAW: None.
- `amount: Decimal | None`
  - For DEPOSIT/WITHDRAW: cash amount.
  - For BUY/SELL: total cash impact (e.g., `quantity * price`) can be stored optionally; design allows either:
    - store `amount` as the computed cash delta, or
    - compute from `quantity * price` later.
  - Choose one and keep consistent; recommended: store both `quantity` & `price`, compute amount when needed.

**Notes**
- Storing `price` at execution time ensures historical P/L can be computed consistently even if current prices change. However, requirement primarily needs “holdings and P/L at any point in time” based on current price; storing execution price is still valuable for auditability and later enhancements.

---

## Price Function

### `def get_share_price(symbol: str) -> float`
Test implementation returning fixed prices:

- AAPL -> 180.00
- TSLA -> 250.00
- GOOGL -> 140.00

**Behavior**
- Normalize symbol (strip, upper).
- Raise `InvalidSymbolError` (or `KeyError`/`ValueError` if you prefer) if unknown.
- Return a Python `float` as specified; `Account` should convert to `Decimal` internally.

---

## Primary Class: `Account`

### Responsibilities
- Maintain:
  - account identity
  - immutable chronological transaction list
- Provide:
  - methods to mutate state via new transactions (deposit/withdraw/buy/sell)
  - reporting methods that compute derived state at any timestamp

### Constructor

#### `def __init__(self, user_id: str, *, account_id: str | None = None, created_at: datetime | None = None) -> None`
**Parameters**
- `user_id`: external user identifier
- `account_id` (optional): if None, generate UUID
- `created_at` (optional): default = now (UTC)

**Internal State**
- `_user_id: str`
- `_account_id: str`
- `_created_at: datetime`
- `_transactions: list[Transaction]` initially empty

**Invariants**
- All timestamps stored as UTC-aware datetimes.
- `_transactions` always sorted by timestamp insertion order; if out-of-order inserts are allowed, design should sort. Recommended: enforce append-only in time order.

---

## Mutation Methods (create transactions)

### `def deposit(self, amount: float | Decimal, *, timestamp: datetime | None = None, note: str | None = None) -> Transaction`
Adds cash to account.

**Validation**
- amount > 0
- timestamp default: now UTC

**Effects**
- Append DEPOSIT transaction

**Returns**
- The created `Transaction`

---

### `def withdraw(self, amount: float | Decimal, *, timestamp: datetime | None = None, note: str | None = None) -> Transaction`
Withdraws cash from account.

**Validation**
- amount > 0
- Ensure `cash_balance(as_of=timestamp)` >= amount  
  - Otherwise raise `InsufficientFundsError`.

**Effects**
- Append WITHDRAW transaction

**Returns**
- The created `Transaction`

---

### `def buy(self, symbol: str, quantity: float | Decimal, *, timestamp: datetime | None = None) -> Transaction`
Records purchase of shares.

**Validation**
- `symbol` non-empty; normalized to uppercase
- `quantity > 0`
- Fetch current execution price: `price = Decimal(str(get_share_price(symbol)))`
- Compute `cost = price * quantity`
- Ensure `cash_balance(as_of=timestamp)` >= cost  
  - else raise `InsufficientFundsError`

**Effects**
- Append BUY transaction with `symbol`, `quantity`, and `price`

**Returns**
- The created `Transaction`

---

### `def sell(self, symbol: str, quantity: float | Decimal, *, timestamp: datetime | None = None) -> Transaction`
Records sale of shares.

**Validation**
- `symbol` non-empty; normalized to uppercase
- `quantity > 0`
- Ensure `holdings(as_of=timestamp)[symbol] >= quantity`  
  - else raise `InsufficientHoldingsError`
- Fetch current execution price: `price = Decimal(str(get_share_price(symbol)))`

**Effects**
- Append SELL transaction with `symbol`, `quantity`, and `price`

**Returns**
- The created `Transaction`

---

## Query & Reporting Methods

### Common timestamp argument
All reporting methods accept:
- `as_of: datetime | None = None`
  - None means “now” (i.e., include all transactions)

Internally, these methods should compute derived state by iterating through `_transactions` filtered by `tx.timestamp <= as_of_time`.

---

### `def transactions(self, *, start: datetime | None = None, end: datetime | None = None) -> list[Transaction]`
Returns transactions in chronological order.

**Behavior**
- If no filters: return all.
- If `start` supplied: include tx with `timestamp >= start`
- If `end` supplied: include tx with `timestamp <= end`
- Return a shallow copy to prevent external mutation.

---

### `def holdings(self, *, as_of: datetime | None = None) -> dict[str, Decimal]`
Returns share quantities per symbol at the time.

**Behavior**
- Replay BUY/SELL up to `as_of`
- Result includes only symbols with non-zero quantities (recommended)
- Ensure no negative quantities via validation in `sell`

---

### `def cash_balance(self, *, as_of: datetime | None = None) -> Decimal`
Returns cash at the time.

**Replay rules**
- DEPOSIT: +amount
- WITHDRAW: -amount
- BUY: - (price * quantity)
- SELL: + (price * quantity)

---

### `def portfolio_value(self, *, as_of: datetime | None = None) -> Decimal`
Returns market value of holdings at the time using **current** `get_share_price` for each symbol in holdings.

**Computation**
- `sum(qty * Decimal(str(get_share_price(symbol))))` over holdings at `as_of`

**Note**
- This uses “current” price at runtime, even for historical `as_of`. This matches requirement constraints (only current price function is specified). If later enhanced with historical pricing, this method signature can remain stable.

---

### `def equity_value(self, *, as_of: datetime | None = None) -> Decimal`
Returns total account value = cash + portfolio.

---

### `def net_contributions(self, *, as_of: datetime | None = None) -> Decimal`
(Recommended helper) Returns `total_deposits - total_withdrawals` up to the time.

---

### `def profit_loss(self, *, as_of: datetime | None = None) -> Decimal`
Returns P/L at time:

- `equity_value(as_of) - net_contributions(as_of)`

---

### `def profit_loss_pct(self, *, as_of: datetime | None = None) -> Decimal | None`
Returns percentage P/L:

- If `net_contributions(as_of) == 0`: return `None`
- Else `(profit_loss / net_contributions) * 100`

---

## Internal Helpers (Private)

### `def _now_utc(self) -> datetime`
Returns timezone-aware `datetime.now(timezone.utc)`.

### `def _to_decimal(self, value: float | Decimal) -> Decimal`
Converts numeric inputs; recommended:
- If float: `Decimal(str(value))` to reduce binary float artifacts

### `def _normalize_symbol(self, symbol: str) -> str`
- strip + upper
- validate non-empty, optionally regex `[A-Z.]+` per platform rules

### `def _iter_tx_up_to(self, as_of: datetime | None) -> Iterable[Transaction]`
Yields transactions `<= as_of` or all if `None`.

### `def _validate_positive_quantity(self, quantity: Decimal) -> None`
Raise `InvalidQuantityError` if `quantity <= 0`.

---

## State Replay Algorithm (Core of “as of” queries)

All “as_of” queries depend on a deterministic replay:

- Initialize `cash = Decimal("0")`
- Initialize `pos = defaultdict(Decimal)` (symbol -> qty)
- For each transaction up to `as_of`:
  - DEPOSIT: `cash += amount`
  - WITHDRAW: `cash -= amount`
  - BUY: `cash -= price*qty`; `pos[symbol] += qty`
  - SELL: `cash += price*qty`; `pos[symbol] -= qty`
- Return requested outputs (cash, positions)

This ensures:
- Holdings at any point in time
- Cash at any point in time
- Proper enforcement when adding a new transaction with a timestamp (if you allow backdated orders, you must validate against balances/holdings at that timestamp by replaying up to that timestamp).

---

## Validation & Constraints

### Prevent negative cash
- `withdraw`: check `cash_balance(as_of=timestamp)` before appending.
- `buy`: check `cash_balance(as_of=timestamp)` vs computed cost.

### Prevent selling more than held
- `sell`: check `holdings(as_of=timestamp).get(symbol, 0)` vs quantity.

### Quantity rules
- Enforce `quantity > 0`.
- Optional: if fractional shares are not allowed, enforce `quantity == int(quantity)`.

### Timestamp rules
- If allowing custom timestamps:
  - Must be timezone-aware UTC or converted to UTC.
  - Backdated transactions are allowed only if validation uses “as_of=timestamp” state.
  - If you want to keep it simpler: disallow backdating and require timestamp omitted; then all transactions are chronological and validation is simpler. This design supports both.

---

## Example Usage (for tests / UI wiring)

- Create account:
  - `acct = Account(user_id="user-123")`
- Deposit:
  - `acct.deposit(10000)`
- Buy:
  - `acct.buy("AAPL", 10)`
- Sell:
  - `acct.sell("AAPL", 3)`
- Query:
  - `acct.holdings()`
  - `acct.cash_balance()`
  - `acct.portfolio_value()`
  - `acct.profit_loss()`
  - `acct.transactions()`

---

## Implementation Notes (Engineer Guidance)
- Keep module self-contained:
  - Only use stdlib: `dataclasses`, `datetime`, `decimal`, `enum`, `uuid`, `typing`, `collections`.
- Favor immutability in `Transaction` to keep audit trail safe.
- Provide deterministic decimal context/quantization policy if desired (e.g., cents):
  - Optionally quantize money to `Decimal("0.01")` in each operation.
- Ensure that `get_share_price` is at module scope so it can be replaced/mocked in tests.

---

## Final Deliverable Checklist (What engineer should implement in `accounts.py`)
- [ ] `get_share_price(symbol)` with fixed test prices
- [ ] `TransactionType` enum
- [ ] `Transaction` dataclass
- [ ] Exception classes listed above
- [ ] `Account` class with all signatures above
- [ ] Full validation and replay-based reporting with `as_of`
- [ ] No external dependencies beyond stdlib
```