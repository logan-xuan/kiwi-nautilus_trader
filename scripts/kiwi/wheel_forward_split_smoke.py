#!/usr/bin/env python3
"""Installed-wheel smoke for Kiwi's atomic forward-split API."""

from __future__ import annotations

import json
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import PositionId
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.position import Position
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.test_kit.stubs.data import TestDataStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from nautilus_trader.test_kit.stubs.identifiers import TestIdStubs


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    manifest = json.loads((ROOT / "KIWI_FORK.json").read_text())
    assert version("nautilus_trader") == manifest["version"]

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    instrument = TestInstrumentProvider.equity("AAPL", "XNAS")
    engine.add_venue(
        venue=instrument.id.venue,
        oms_type=OmsType.HEDGING,
        account_type=AccountType.CASH,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
        fill_model=FillModel(),
    )
    engine.add_instrument(instrument)

    order = OrderFactory(
        trader_id=TestIdStubs.trader_id(),
        strategy_id=TestIdStubs.strategy_id(),
        clock=TestClock(),
    ).market(instrument.id, OrderSide.BUY, Quantity.from_int(25))
    fill = TestEventStubs.order_filled(
        order,
        instrument=instrument,
        position_id=PositionId("P-KIWI-WHEEL-SPLIT"),
        last_px=Price.from_str("150.13"),
    )
    position = Position(instrument=instrument, fill=fill)
    engine.kernel.cache.add_position(position, OmsType.HEDGING)
    realized_pnl_before = position.realized_pnl
    commissions_before = position.commissions().copy()
    event_count_before = position.event_count
    trade_ids_before = position.trade_ids.copy()
    adjustments = []
    cash_balances = []

    def native_batches():
        yield [TestDataStubs.quote_tick(instrument, 150.00, 150.01, ts_init=1)]
        cash_before = engine.portfolio.account(instrument.id.venue).balance_total(USD)
        adjustments.extend(
            engine.apply_forward_split(
                instrument.id,
                2,
                "kiwi-wheel-smoke-2-for-1",
                2,
            ),
        )
        cash_balances.append((
            cash_before,
            engine.portfolio.account(instrument.id.venue).balance_total(USD),
        ))
        yield [TestDataStubs.quote_tick(instrument, 75.00, 75.01, ts_init=3)]

    try:
        engine.add_data_iterator("kiwi-wheel-smoke", native_batches())
        engine.run()

        assert len(adjustments) == 1
        assert position.quantity == Quantity.from_int(50)
        assert abs(position.avg_px_open - 75.065) < 1e-12
        assert engine.portfolio.net_position(instrument.id) == Decimal(50)
        assert cash_balances == [(Money(1_000_000, USD), Money(1_000_000, USD))]
        assert position.realized_pnl == realized_pnl_before
        assert position.commissions() == commissions_before
        assert position.event_count == event_count_before
        assert position.trade_ids == trade_ids_before
    finally:
        engine.dispose()

    print("installed Kiwi forward-split smoke passed")


if __name__ == "__main__":
    main()
