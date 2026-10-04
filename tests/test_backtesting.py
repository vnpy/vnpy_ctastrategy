from datetime import date, datetime
from typing import cast

from vnpy.trader.constant import Direction, Exchange, Interval, Offset, Status
from vnpy.trader.object import BarData, OrderData, TradeData

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy_ctastrategy.base import STOPORDER_PREFIX, StopOrder, StopOrderStatus
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


class RecordingStrategy(CtaTemplate):
    def __init__(
        self,
        cta_engine: object,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bar_count: int = 0
        self.vt_orderids: list[str] = []

    def on_init(self) -> None:
        return


class LimitShortStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.short(105, 1)


class LimitBuyStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.buy(100, 1)


class ScaledLimitBuyStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.buy(100, 1)
        elif self.bar_count == 2:
            self.buy(90, 1)


class StopBuyStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.vt_orderids = self.buy(110, 1, stop=True)


class CancelLimitStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.vt_orderids = self.buy(100, 1)
        elif self.bar_count == 2:
            self.cancel_order(self.vt_orderids[0])


class CancelStopStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.vt_orderids = self.buy(110, 1, stop=True)
        elif self.bar_count == 2:
            self.cancel_order(self.vt_orderids[0])


class RoundTripStrategy(RecordingStrategy):
    def on_bar(self, bar: BarData) -> None:
        self.bar_count += 1
        if self.bar_count == 1:
            self.buy(100, 1)
            self.sell(100, 1)


def prepare_engine(
    strategy_class: type[CtaTemplate],
    rate: float = 0,
) -> BacktestingEngine:
    engine: BacktestingEngine = BacktestingEngine()
    engine.output = swallow_output  # type: ignore[method-assign]
    engine.set_parameters(
        vt_symbol=VT_SYMBOL,
        interval=Interval.MINUTE,
        start=datetime(2024, 1, 2),
        rate=rate,
        slippage=0,
        size=10,
        pricetick=1,
        capital=1_000_000,
        end=datetime(2024, 1, 4),
    )
    engine.add_strategy(strategy_class, {})
    engine.strategy.on_init()
    engine.strategy.inited = True
    engine.strategy.on_start()
    engine.strategy.trading = True
    return engine


class TestBacktestingOrders:
    def test_limit_short_stays_active_until_high_crosses(self) -> None:
        # 限价空单用 high 撮合。high 低于委托价时留在 active_limit_orders，触及后才成交。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 100, 104, 100, 100)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 104, 105, 103, 104)

        engine: BacktestingEngine = prepare_engine(LimitShortStrategy)
        engine.new_bar(bar_1)
        assert list(engine.active_limit_orders) == ["BACKTESTING.1"]
        assert engine.trades == {}

        engine.new_bar(bar_2)
        assert list(engine.active_limit_orders) == ["BACKTESTING.1"]
        assert engine.limit_orders["BACKTESTING.1"].status == Status.NOTTRADED
        assert engine.trade_count == 0
        assert engine.strategy.pos == 0

        engine.new_bar(bar_3)
        assert engine.active_limit_orders == {}
        order: OrderData = engine.limit_orders["BACKTESTING.1"]
        assert order.direction == Direction.SHORT
        assert order.offset == Offset.OPEN
        assert order.status == Status.ALLTRADED
        trade: TradeData = engine.trades["BACKTESTING.1"]
        assert trade.price == max(order.price, bar_3.open_price)
        assert trade.direction == Direction.SHORT
        assert trade.volume == 1
        assert engine.strategy.pos == -1

    def test_limit_buy_does_not_fill_when_low_is_zero(self) -> None:
        # 限价多单要求 low > 0。low 为 0 时即使委托价更高也不成交。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 10, 20, 0, 10)

        engine: BacktestingEngine = prepare_engine(LimitBuyStrategy)
        engine.new_bar(bar_1)
        engine.new_bar(bar_2)

        assert list(engine.active_limit_orders) == ["BACKTESTING.1"]
        order: OrderData = engine.limit_orders["BACKTESTING.1"]
        assert order.direction == Direction.LONG
        assert order.status == Status.NOTTRADED
        assert order.traded == 0
        assert engine.trades == {}
        assert engine.strategy.pos == 0

    def test_limit_buy_fill_price_is_min_of_order_and_open(self) -> None:
        # 成交价是 min(委托价, open)。第一笔 open 更低，第二笔 open 更高。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 98, 103, 97, 99)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 95, 96, 89, 94)

        engine: BacktestingEngine = prepare_engine(ScaledLimitBuyStrategy)
        engine.new_bar(bar_1)
        engine.new_bar(bar_2)
        engine.new_bar(bar_3)

        first_order: OrderData = engine.limit_orders["BACKTESTING.1"]
        second_order: OrderData = engine.limit_orders["BACKTESTING.2"]
        first_trade: TradeData = engine.trades["BACKTESTING.1"]
        second_trade: TradeData = engine.trades["BACKTESTING.2"]
        assert first_order.status == Status.ALLTRADED
        assert second_order.status == Status.ALLTRADED
        assert first_trade.price == min(first_order.price, bar_2.open_price)
        assert second_trade.price == min(second_order.price, bar_3.open_price)
        assert first_trade.price == 98
        assert second_trade.price == 90
        assert first_trade.direction == Direction.LONG
        assert second_trade.direction == Direction.LONG

    def test_stop_buy_triggers_on_bar_high(self) -> None:
        # 停止买单看 bar.high，不用 last_price。high 低于触发价时留在 active_stop_orders。
        # low 仍低于触发价时，只要 high 触及，同一步生成已全部成交的限价单和成交。
        stop_orderid: str = f"{STOPORDER_PREFIX}.1"
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 100, 109, 100, 105)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 108, 110, 107, 109)

        engine: BacktestingEngine = prepare_engine(StopBuyStrategy)
        engine.new_bar(bar_1)
        assert list(engine.active_stop_orders) == [stop_orderid]
        assert engine.stop_orders[stop_orderid].status == StopOrderStatus.WAITING
        assert engine.limit_orders == {}
        assert engine.trades == {}

        engine.new_bar(bar_2)
        assert list(engine.active_stop_orders) == [stop_orderid]
        assert engine.stop_orders[stop_orderid].status == StopOrderStatus.WAITING
        assert engine.trades == {}
        assert engine.strategy.pos == 0

        engine.new_bar(bar_3)
        stop_order: StopOrder = engine.stop_orders[stop_orderid]
        assert stop_orderid not in engine.active_stop_orders
        assert stop_order.status == StopOrderStatus.TRIGGERED
        assert stop_order.vt_orderids == ["BACKTESTING.1"]

        order: OrderData = engine.limit_orders["BACKTESTING.1"]
        assert order.status == Status.ALLTRADED
        assert order.traded == order.volume
        assert order.direction == Direction.LONG
        assert engine.active_limit_orders == {}

        trade: TradeData = engine.trades["BACKTESTING.1"]
        assert trade.direction == Direction.LONG
        assert trade.volume == 1
        assert trade.price == max(stop_order.price, bar_3.open_price)
        assert engine.strategy.pos == 1
        assert engine.trade_count == 1

    def test_cancel_unfilled_limit_order(self) -> None:
        # 第二根未触及。撤单后第三根虽然能成交，也不再产生成交。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 102, 103, 101, 102)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 100, 103, 99, 100)

        engine: BacktestingEngine = prepare_engine(CancelLimitStrategy)
        engine.new_bar(bar_1)
        engine.new_bar(bar_2)
        engine.new_bar(bar_3)

        order: OrderData = engine.limit_orders["BACKTESTING.1"]
        assert order.status == Status.CANCELLED
        assert engine.active_limit_orders == {}
        assert engine.trades == {}
        assert engine.trade_count == 0
        assert engine.strategy.pos == 0

    def test_cancel_stop_order_with_stop_prefix(self) -> None:
        # 停止单号带 STOP 前缀，撤单走停止单而不是限价单。
        stop_orderid: str = f"{STOPORDER_PREFIX}.1"
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 2, 9, 1), 100, 109, 100, 105)
        bar_3: BarData = make_bar(datetime(2024, 1, 2, 9, 2), 100, 120, 100, 110)

        engine: BacktestingEngine = prepare_engine(CancelStopStrategy)
        strategy: CancelStopStrategy = cast(CancelStopStrategy, engine.strategy)
        engine.new_bar(bar_1)
        assert strategy.vt_orderids == [stop_orderid]
        engine.new_bar(bar_2)
        engine.new_bar(bar_3)

        stop_order: StopOrder = engine.stop_orders[stop_orderid]
        assert stop_order.status == StopOrderStatus.CANCELLED
        assert stop_orderid not in engine.active_stop_orders
        assert engine.limit_orders == {}
        assert engine.trades == {}
        assert engine.strategy.pos == 0

    def test_calculate_result_round_trip_has_commission(self) -> None:
        # 两根 K 线按时间排列。第一根同时开平，第二根成交，当日回合后持仓回到 0。
        bar_1: BarData = make_bar(datetime(2024, 1, 2, 9, 0), 100, 100, 100, 100)
        bar_2: BarData = make_bar(datetime(2024, 1, 3, 9, 0), 100, 102, 98, 101)
        rate: float = 0.01

        engine: BacktestingEngine = prepare_engine(RoundTripStrategy, rate)
        engine.new_bar(bar_1)
        engine.new_bar(bar_2)
        engine.calculate_result()

        assert list(engine.daily_df.index) == [date(2024, 1, 2), date(2024, 1, 3)]
        assert engine.daily_df.loc[date(2024, 1, 2), "trade_count"] == 0
        assert engine.daily_df.loc[date(2024, 1, 2), "end_pos"] == 0
        assert engine.daily_df.loc[date(2024, 1, 3), "trade_count"] == 2
        assert engine.daily_df.loc[date(2024, 1, 3), "end_pos"] == 0
        assert engine.daily_df.loc[date(2024, 1, 3), "commission"] == 2 * 1 * 10 * 100 * rate
        assert engine.strategy.pos == 0
