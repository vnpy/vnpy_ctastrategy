"""ATR与RSI策略。"""

import numpy as np

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


class AtrRsiStrategy(CtaTemplate):
    """用ATR与RSI开仓，并用跟踪止损平仓的策略。"""

    author = "用Python的交易员"

    atr_length: int = 22
    atr_ma_length: int = 10
    rsi_length: int = 5
    rsi_entry: int = 16
    trailing_percent: float = 0.8
    fixed_size: int = 1

    atr_value: float = 0
    atr_ma: float = 0
    rsi_value: float = 0
    rsi_buy: float = 0
    rsi_sell: float = 0
    intra_trade_high: float = 0
    intra_trade_low: float = 0

    parameters = [
        "atr_length",
        "atr_ma_length",
        "rsi_length",
        "rsi_entry",
        "trailing_percent",
        "fixed_size"
    ]
    variables = [
        "atr_value",
        "atr_ma",
        "rsi_value",
        "rsi_buy",
        "rsi_sell",
        "intra_trade_high",
        "intra_trade_low"
    ]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.bg: BarGenerator = BarGenerator(self.on_bar)
        self.am: ArrayManager = ArrayManager()

        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry

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
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.cancel_all()

        am: ArrayManager = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        atr_array: np.ndarray = am.atr(self.atr_length, array=True)
        self.atr_value = atr_array[-1]
        self.atr_ma = atr_array[-self.atr_ma_length:].mean()
        self.rsi_value = am.rsi(self.rsi_length)

        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            if self.atr_value > self.atr_ma:
                if self.rsi_value > self.rsi_buy:
                    self.buy(bar.close_price + 5, self.fixed_size)
                elif self.rsi_value < self.rsi_sell:
                    self.short(bar.close_price - 5, self.fixed_size)

        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            long_stop: float = self.intra_trade_high * (1 - self.trailing_percent / 100)
            self.sell(long_stop, abs(self.pos), stop=True)

        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.intra_trade_high = bar.high_price

            short_stop: float = self.intra_trade_low * (1 + self.trailing_percent / 100)
            self.cover(short_stop, abs(self.pos), stop=True)

        self.put_event()

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
