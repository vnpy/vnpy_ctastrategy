"""多周期策略。"""

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class MultiTimeframeStrategy(CtaTemplate):
    """用15分钟均线方向过滤，并在5分钟RSI上开平仓的策略。"""
    author: str = "用Python的交易员"

    rsi_signal: int = 20
    rsi_window: int = 14
    fast_window: int = 5
    slow_window: int = 20
    fixed_size: int = 1

    rsi_value: float = 0
    rsi_long: float = 0
    rsi_short: float = 0
    fast_ma: float = 0
    slow_ma: float = 0
    ma_trend: float = 0

    parameters: list[str] = ["rsi_signal", "rsi_window",
                  "fast_window", "slow_window",
                  "fixed_size"]

    variables: list[str] = ["rsi_value", "rsi_long", "rsi_short",
                 "fast_ma", "slow_ma", "ma_trend"]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.rsi_long: float = 50 + self.rsi_signal
        self.rsi_short: float = 50 - self.rsi_signal

        self.bg5: BarGenerator = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am5: ArrayManager = ArrayManager()

        self.bg15: BarGenerator = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am15: ArrayManager = ArrayManager()

        self.load_bar(10)

    def on_start(self) -> None:
        """
        策略启动时的回调。
        """
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """
        策略停止时的回调。
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        self.bg5.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.bg5.update_bar(bar)
        self.bg15.update_bar(bar)

    def on_5min_bar(self, bar: BarData) -> None:
        """在5分钟K线上按均线方向和RSI开平仓。"""
        self.cancel_all()

        self.am5.update_bar(bar)
        if not self.am5.inited:
            return

        if not self.ma_trend:
            return

        self.rsi_value = self.am5.rsi(self.rsi_window)

        if self.pos == 0:
            if self.ma_trend > 0 and self.rsi_value >= self.rsi_long:
                self.buy(bar.close_price + 5, self.fixed_size)
            elif self.ma_trend < 0 and self.rsi_value <= self.rsi_short:
                self.short(bar.close_price - 5, self.fixed_size)

        elif self.pos > 0:
            if self.ma_trend < 0 or self.rsi_value < 50:
                self.sell(bar.close_price - 5, abs(self.pos))

        elif self.pos < 0:
            if self.ma_trend > 0 or self.rsi_value > 50:
                self.cover(bar.close_price + 5, abs(self.pos))

        self.put_event()

    def on_15min_bar(self, bar: BarData) -> None:
        """用15分钟快慢均线更新趋势方向。"""
        self.am15.update_bar(bar)
        if not self.am15.inited:
            return

        self.fast_ma = self.am15.sma(self.fast_window)
        self.slow_ma = self.am15.sma(self.slow_window)

        if self.fast_ma > self.slow_ma:
            self.ma_trend = 1
        else:
            self.ma_trend = -1

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        pass

    def on_trade(self, trade: TradeData) -> None:
        """
        新成交数据更新时的回调。
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """
        停止单更新时的回调。
        """
        pass
