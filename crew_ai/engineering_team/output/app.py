from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from accounts import (
    Account,
    AccountError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidQuantityError,
    InvalidSymbolError,
    get_share_price,
)


APP_TITLE = "Trading Sim Account (Demo)"
DEFAULT_USER_ID = "demo_user"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt_money(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'))}"


def _fmt_qty(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.00000001'))}".rstrip("0").rstrip(".")


def _safe_decimal_str(x: Any) -> str:
    try:
        if isinstance(x, Decimal):
            return str(x)
        return str(Decimal(str(x)))
    except Exception:
        return str(x)


def _make_account(user_id: str) -> Account:
    user_id = (user_id or "").strip()
    if not user_id:
        user_id = DEFAULT_USER_ID
    return Account(user_id=user_id)


def _tx_to_row(tx) -> Dict[str, Any]:
    d = asdict(tx)
    # Convert Enum and datetime and Decimal to display-friendly strings
    d["type"] = getattr(tx.type, "value", str(tx.type))
    d["timestamp"] = tx.timestamp.isoformat(timespec="seconds")
    for k in ("quantity", "price", "amount"):
        if d.get(k) is not None:
            d[k] = _safe_decimal_str(d[k])
    return {
        "timestamp": d.get("timestamp", ""),
        "type": d.get("type", ""),
        "symbol": d.get("symbol", "") or "",
        "quantity": d.get("quantity", "") or "",
        "price": d.get("price", "") or "",
        "amount": d.get("amount", "") or "",
        "note": d.get("note", "") or "",
        "id": d.get("id", "") or "",
    }


def _holdings_table(acct: Account) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    h = acct.holdings()
    for sym in sorted(h.keys()):
        qty = h[sym]
        if qty == 0:
            continue
        price = Decimal(str(get_share_price(sym))).quantize(Decimal("0.01"))
        value = (price * qty).quantize(Decimal("0.01"))
        rows.append(
            {
                "symbol": sym,
                "quantity": _fmt_qty(qty),
                "price": _fmt_money(price),
                "value": _fmt_money(value),
            }
        )
    return rows


def _transactions_table(acct: Account) -> List[Dict[str, Any]]:
    return [_tx_to_row(tx) for tx in acct.transactions()]


def _build_snapshot(acct: Account) -> Tuple[str, str, str, str, str]:
    cash = acct.cash_balance()
    port = acct.portfolio_value()
    eq = acct.equity_value()
    pl = acct.profit_loss()
    pl_pct = acct.profit_loss_pct()
    pl_pct_s = "—" if pl_pct is None else f"{pl_pct}%"
    return (_fmt_money(cash), _fmt_money(port), _fmt_money(eq), _fmt_money(pl), pl_pct_s)


def _status_ok(msg: str) -> str:
    return f"OK • {msg} • { _now_iso_utc() }"


def _status_err(msg: str) -> str:
    return f"ERROR • {msg} • { _now_iso_utc() }"


def ui_create_account(user_id: str) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        acct = _make_account(user_id)
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        status = _status_ok(f"Created account for user_id={acct.user_id} (account_id={acct.account_id})")
        return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)
    except Exception as e:
        acct = _make_account(DEFAULT_USER_ID)
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        return acct, _status_err(str(e)), cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def _require_account(acct: Optional[Account]) -> Account:
    if acct is None:
        return _make_account(DEFAULT_USER_ID)
    return acct


def ui_deposit(acct: Optional[Account], amount: str, note: str) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _require_account(acct)
    try:
        tx = acct.deposit(amount, note=(note or None))
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        status = _status_ok(f"Deposit {_fmt_money(tx.amount or Decimal('0'))}")
        return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)
    except (InvalidQuantityError, AccountError) as e:
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        return acct, _status_err(str(e)), cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def ui_withdraw(acct: Optional[Account], amount: str, note: str) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _require_account(acct)
    try:
        tx = acct.withdraw(amount, note=(note or None))
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        status = _status_ok(f"Withdraw {_fmt_money(tx.amount or Decimal('0'))}")
        return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)
    except (InsufficientFundsError, InvalidQuantityError, AccountError) as e:
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        return acct, _status_err(str(e)), cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def ui_buy(acct: Optional[Account], symbol: str, quantity: str, note: str) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _require_account(acct)
    sym = (symbol or "").strip().upper()
    try:
        tx = acct.buy(sym, quantity, note=(note or None))
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        status = _status_ok(
            f"Buy {tx.symbol} x{_fmt_qty(tx.quantity or Decimal('0'))} @ {_fmt_money(tx.price or Decimal('0'))} (amount {_fmt_money(tx.amount or Decimal('0'))})"
        )
        return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)
    except (InvalidSymbolError, InvalidQuantityError, InsufficientFundsError, AccountError) as e:
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        return acct, _status_err(str(e)), cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def ui_sell(acct: Optional[Account], symbol: str, quantity: str, note: str) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _require_account(acct)
    sym = (symbol or "").strip().upper()
    try:
        tx = acct.sell(sym, quantity, note=(note or None))
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        status = _status_ok(
            f"Sell {tx.symbol} x{_fmt_qty(tx.quantity or Decimal('0'))} @ {_fmt_money(tx.price or Decimal('0'))} (amount {_fmt_money(tx.amount or Decimal('0'))})"
        )
        return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)
    except (InvalidSymbolError, InvalidQuantityError, InsufficientHoldingsError, AccountError) as e:
        cash, port, eq, pl, pl_pct = _build_snapshot(acct)
        return acct, _status_err(str(e)), cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def ui_refresh(acct: Optional[Account]) -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _require_account(acct)
    cash, port, eq, pl, pl_pct = _build_snapshot(acct)
    status = _status_ok("Refreshed")
    return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def ui_reset_demo() -> Tuple[Account, str, str, str, str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    acct = _make_account(DEFAULT_USER_ID)
    cash, port, eq, pl, pl_pct = _build_snapshot(acct)
    status = _status_ok("Reset demo state (new empty account)")
    return acct, status, cash, port, eq, pl, pl_pct, _holdings_table(acct), _transactions_table(acct)


def _price_hint(symbol: str) -> str:
    sym = (symbol or "").strip().upper()
    if not sym:
        return "Price: —"
    try:
        p = Decimal(str(get_share_price(sym))).quantize(Decimal("0.01"))
        return f"Price: {sym} = {_fmt_money(p)}"
    except Exception as e:
        return f"Price: {sym} unavailable ({e})"


def build_app() -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft(), fill_height=True) as demo:
        acct_state = gr.State(value=_make_account(DEFAULT_USER_ID))

        gr.Markdown(
            f"# {APP_TITLE}\n"
            "Prototype UI demonstrating the `Account` backend.\n\n"
            "Supported symbols (fixed test prices): **AAPL**, **TSLA**, **GOOGL**."
        )

        with gr.Row():
            user_id = gr.Textbox(label="User ID (single-user demo)", value=DEFAULT_USER_ID, scale=2)
            create_btn = gr.Button("Create / Replace Account", variant="primary", scale=1)
            reset_btn = gr.Button("Reset Demo", variant="secondary", scale=1)

        status = gr.Textbox(label="Status", value=_status_ok("Ready"), interactive=False)

        with gr.Row():
            cash_out = gr.Textbox(label="Cash Balance", interactive=False)
            portfolio_out = gr.Textbox(label="Portfolio Value", interactive=False)
            equity_out = gr.Textbox(label="Equity (Cash + Portfolio)", interactive=False)

        with gr.Row():
            pl_out = gr.Textbox(label="Profit / Loss", interactive=False)
            pl_pct_out = gr.Textbox(label="P/L % (vs. net contributions)", interactive=False)
            refresh_btn = gr.Button("Refresh", variant="secondary")

        with gr.Tabs():
            with gr.Tab("Funds"):
                with gr.Row():
                    dep_amount = gr.Textbox(label="Deposit Amount", placeholder="e.g. 10000")
                    dep_note = gr.Textbox(label="Note (optional)", placeholder="e.g. initial funding")
                    dep_btn = gr.Button("Deposit", variant="primary")

                with gr.Row():
                    wd_amount = gr.Textbox(label="Withdraw Amount", placeholder="e.g. 500")
                    wd_note = gr.Textbox(label="Note (optional)")
                    wd_btn = gr.Button("Withdraw", variant="primary")

            with gr.Tab("Trade"):
                with gr.Row():
                    symbol = gr.Dropdown(
                        label="Symbol",
                        choices=["AAPL", "TSLA", "GOOGL"],
                        value="AAPL",
                        allow_custom_value=True,
                        interactive=True,
                    )
                    qty = gr.Textbox(label="Quantity", placeholder="e.g. 1 or 0.25")
                    trade_note = gr.Textbox(label="Note (optional)", placeholder="e.g. thesis / reason")

                with gr.Row():
                    price_hint = gr.Markdown(value=_price_hint("AAPL"))
                with gr.Row():
                    buy_btn = gr.Button("Buy", variant="primary")
                    sell_btn = gr.Button("Sell", variant="secondary")

            with gr.Tab("Holdings"):
                holdings_df = gr.Dataframe(
                    label="Current Holdings",
                    headers=["symbol", "quantity", "price", "value"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    row_count=(1, "dynamic"),
                    col_count=(4, "fixed"),
                )

            with gr.Tab("Transactions"):
                tx_df = gr.Dataframe(
                    label="Transactions (append-only)",
                    headers=["timestamp", "type", "symbol", "quantity", "price", "amount", "note", "id"],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    row_count=(1, "dynamic"),
                    col_count=(8, "fixed"),
                )

        def _apply_outputs(result):
            return result

        outputs = [
            acct_state,
            status,
            cash_out,
            portfolio_out,
            equity_out,
            pl_out,
            pl_pct_out,
            holdings_df,
            tx_df,
        ]

        create_btn.click(
            fn=ui_create_account,
            inputs=[user_id],
            outputs=outputs,
            api_name="create_account",
        )

        reset_btn.click(
            fn=ui_reset_demo,
            inputs=[],
            outputs=outputs,
            api_name="reset_demo",
        )

        dep_btn.click(
            fn=ui_deposit,
            inputs=[acct_state, dep_amount, dep_note],
            outputs=outputs,
            api_name="deposit",
        )

        wd_btn.click(
            fn=ui_withdraw,
            inputs=[acct_state, wd_amount, wd_note],
            outputs=outputs,
            api_name="withdraw",
        )

        buy_btn.click(
            fn=ui_buy,
            inputs=[acct_state, symbol, qty, trade_note],
            outputs=outputs,
            api_name="buy",
        )

        sell_btn.click(
            fn=ui_sell,
            inputs=[acct_state, symbol, qty, trade_note],
            outputs=outputs,
            api_name="sell",
        )

        refresh_btn.click(
            fn=ui_refresh,
            inputs=[acct_state],
            outputs=outputs,
            api_name="refresh",
        )

        symbol.change(fn=_price_hint, inputs=[symbol], outputs=[price_hint])

        # Initialize displayed metrics/tables from initial state
        demo.load(fn=ui_refresh, inputs=[acct_state], outputs=outputs)

    return demo


if __name__ == "__main__":
    app = build_app()
    app.queue(api_open=False)
    app.launch()