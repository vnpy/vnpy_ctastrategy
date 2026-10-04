from datetime import datetime
from typing import cast

from vnpy.trader.constant import Direction, Exchange, Interval, Offset, Status
from vnpy.trader.object import BarData, TradeData

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy_ctastrategy.template import CtaTemplate


VT_SYMBOL: str = "rb2501.SHFE"
SYMBOL: str = "rb2501"


def swallow_output(msg: str) -> None:
    return


def make_bar(
    dt: datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> BarData:
    return BarData(
        symbol=SYMBOL,
        exchange=Exchange.SHFE,
        datetime=dt,
        interval=Interval.MINUTE,
        volume=1,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        gateway_name="BACKTESTING",
    )


class NextBarCrossStrategy(CtaTemplate):
    def __init__(
        self,
        cta_engine: object,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.pos_at_bar: list[float] = []
        self.trade_count_at_bar: list[int] = []
        self.datetime_at_bar: list[datetime] = []
        self.fill_datetimes: list[datetime | None] = []

    def on_init(self) -> None:
        return

    def on_bar(self, bar: BarData) -> None:
        engine: BacktestingEngine = cast(BacktestingEngine, self.cta_engine)
        self.pos_at_bar.append(self.pos)
        self.trade_count_at_bar.append(engine.trade_count)
        self.datetime_at_bar.append(engine.datetime)
        assert engine.datetime == bar.datetime
        if len(self.datetime_at_bar) == 1:
            self.buy(100, 1)

    def on_trade(self, trade: TradeData) -> None:
        self.fill_datetimes.append(trade.datetime)


class TestBacktestingCross:
    def test_limit_buy_fills_when_bar_low_crosses(self) -> None:
        # new_bar 先撮合再回调。买单在 price >= low 且 low > 0 时成交，下单那根 K 线来不及参与。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 101.5, 102, 101, 101.5)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 100, 103, 99, 101)
        bar_4: BarData = make_bar(datetime(2024, 1, 2, 9, 3), 101, 102, 101, 101)

        engine: BacktestingEngine = BacktestingEngine()
        engine.output = swallow_output  # type: ignore[method-assign]
        engine.set_parameters(
            vt_symbol=VT_SYMBOL,
            interval=Interval.MINUTE,
            start=datetime(2024, 1, 2),
            rate=0,
            slippage=0,
            size=10,
            pricetick=1,
            capital=1_000_000,
            end=datetime(2024, 1, 2, 15, 0),
        )
        engine.add_strategy(NextBarCrossStrategy, {})
        engine.history_data = [bar_1, bar_2, bar_3, bar_4]
        engine.run_backtesting()

        strategy: NextBarCrossStrategy = cast(NextBarCrossStrategy, engine.strategy)
        assert strategy.datetime_at_bar == [
            bar_1.datetime,
            bar_2.datetime,
            bar_3.datetime,
            bar_4.datetime,
        ]
        assert strategy.trade_count_at_bar == [0, 0, 1, 1]
        assert strategy.pos_at_bar == [0, 0, 1, 1]
        assert strategy.fill_datetimes == [bar_3.datetime]
        assert engine.datetime == bar_4.datetime
        assert engine.trade_count == 1
        assert strategy.pos == 1

        assert list(engine.limit_orders) == ["BACKTESTING.1"]
        order = engine.limit_orders["BACKTESTING.1"]
        assert order.direction == Direction.LONG
        assert order.offset == Offset.OPEN
        assert order.status == Status.ALLTRADED

        assert list(engine.trades) == ["BACKTESTING.1"]
        trade: TradeData = engine.trades["BACKTESTING.1"]
        assert trade.datetime == bar_3.datetime
        assert trade.direction == Direction.LONG
        assert trade.offset == Offset.OPEN
        assert trade.volume == 1
