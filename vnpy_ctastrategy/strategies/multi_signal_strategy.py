"""多信号策略。"""

from vnpy_ctastrategy import (
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
    CtaSignal,
    TargetPosTemplate
)


class RsiSignal(CtaSignal):
    """按RSI给出多空信号。"""

    def __init__(self, rsi_window: int, rsi_level: float) -> None:
        """构造函数。"""
        super().__init__()

        self.rsi_window: int = rsi_window
        self.rsi_level: float = rsi_level
        self.rsi_long: float = 50 + self.rsi_level
        self.rsi_short: float = 50 - self.rsi_level

        self.bg: BarGenerator = BarGenerator(self.on_bar)
        self.am: ArrayManager = ArrayManager()

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        rsi_value: float = self.am.rsi(self.rsi_window)

        if rsi_value >= self.rsi_long:
            self.set_signal_pos(1)
        elif rsi_value <= self.rsi_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class CciSignal(CtaSignal):
    """按CCI给出多空信号。"""

    def __init__(self, cci_window: int, cci_level: float) -> None:
        """保存CCI窗口和阈值，并创建K线工具。"""
        super().__init__()

        self.cci_window: int = cci_window
        self.cci_level: float = cci_level
        self.cci_long: float = self.cci_level
        self.cci_short: float = -self.cci_level

        self.bg: BarGenerator = BarGenerator(self.on_bar)
        self.am: ArrayManager = ArrayManager()

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        cci_value: float = self.am.cci(self.cci_window)

        if cci_value >= self.cci_long:
            self.set_signal_pos(1)
        elif cci_value <= self.cci_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class MaSignal(CtaSignal):
    """按5分钟快慢均线给出多空信号。"""

    def __init__(self, fast_window: int, slow_window: int) -> None:
        """保存均线窗口，并创建5分钟K线工具。"""
        super().__init__()

        self.fast_window: int = fast_window
        self.slow_window: int = slow_window

        self.bg: BarGenerator = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am: ArrayManager = ArrayManager()

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar: BarData) -> None:
        """在5分钟K线上按快慢均线设置信号持仓。"""
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        fast_ma: float = self.am.sma(self.fast_window)
        slow_ma: float = self.am.sma(self.slow_window)

        if fast_ma > slow_ma:
            self.set_signal_pos(1)
        elif fast_ma < slow_ma:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class MultiSignalStrategy(TargetPosTemplate):
    """把RSI、CCI和均线信号相加后调整目标持仓。"""

    author: str = "用Python的交易员"

    rsi_window: int = 14
    rsi_level: int = 20
    cci_window: int = 30
    cci_level: int = 10
    fast_window: int = 5
    slow_window: int = 20

    parameters: list[str] = ["rsi_window", "rsi_level", "cci_window",
                  "cci_level", "fast_window", "slow_window"]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.rsi_signal: RsiSignal = RsiSignal(self.rsi_window, self.rsi_level)
        self.cci_signal: CciSignal = CciSignal(self.cci_window, self.cci_level)
        self.ma_signal: MaSignal = MaSignal(self.fast_window, self.slow_window)

        self.signal_pos: dict[str, int] = {
            "rsi": 0,
            "cci": 0,
            "ma": 0
        }

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
        super().on_tick(tick)

        self.rsi_signal.on_tick(tick)
        self.cci_signal.on_tick(tick)
        self.ma_signal.on_tick(tick)

        self.calculate_target_pos()

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        super().on_bar(bar)

        self.rsi_signal.on_bar(bar)
        self.cci_signal.on_bar(bar)
        self.ma_signal.on_bar(bar)

        self.calculate_target_pos()

    def calculate_target_pos(self) -> None:
        """把三个信号持仓相加后设为目标持仓。"""
        self.signal_pos["rsi"] = self.rsi_signal.get_signal_pos()
        self.signal_pos["cci"] = self.cci_signal.get_signal_pos()
        self.signal_pos["ma"] = self.ma_signal.get_signal_pos()

        target_pos: int = 0
        v: int
        for v in self.signal_pos.values():
            target_pos += v

        self.set_target_pos(target_pos)

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        super().on_order(order)

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
