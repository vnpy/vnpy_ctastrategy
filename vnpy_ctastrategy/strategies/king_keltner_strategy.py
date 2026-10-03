"""肯特纳通道策略。"""

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


class KingKeltnerStrategy(CtaTemplate):
    """用肯特纳通道开仓，并用跟踪止损平仓的策略。"""

    author = "用Python的交易员"

    kk_length: int = 11
    kk_dev: float = 1.6
    trailing_percent: float = 0.8
    fixed_size: int = 1

    kk_up: float = 0
    kk_down: float = 0
    intra_trade_high: float = 0
    intra_trade_low: float = 0

    parameters = ["kk_length", "kk_dev", "trailing_percent", "fixed_size"]
    variables = ["kk_up", "kk_down"]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.bg: BarGenerator = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am: ArrayManager = ArrayManager()

        self.long_vt_orderids: list[str] = []
        self.short_vt_orderids: list[str] = []
        self.vt_orderids: list[str] = []

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
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar: BarData) -> None:
        """在5分钟K线上按肯特纳通道发双边停止单，或用跟踪止损平仓。"""
        for orderid in self.vt_orderids:
            self.cancel_order(orderid)
        self.vt_orderids.clear()

        am: ArrayManager = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.kk_up, self.kk_down = am.keltner(self.kk_length, self.kk_dev)

        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price
            self.send_oco_order(self.kk_up, self.kk_down, self.fixed_size)

        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            sell_orderids: list[str] = self.sell(
                self.intra_trade_high * (1 - self.trailing_percent / 100),
                abs(self.pos),
                True
            )
            self.vt_orderids.extend(sell_orderids)

        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            cover_orderids: list[str] = self.cover(
                self.intra_trade_low * (1 + self.trailing_percent / 100),
                abs(self.pos),
                True
            )
            self.vt_orderids.extend(cover_orderids)

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
        if self.pos != 0:
            if self.pos > 0:
                for short_orderid in self.short_vt_orderids:
                    self.cancel_order(short_orderid)

            elif self.pos < 0:
                for buy_orderid in self.long_vt_orderids:
                    self.cancel_order(buy_orderid)

            for orderid in (self.long_vt_orderids + self.short_vt_orderids):
                if orderid in self.vt_orderids:
                    self.vt_orderids.remove(orderid)

        self.put_event()

    def send_oco_order(self, buy_price: float, short_price: float, volume: float) -> None:
        """同时发出买入和卖出停止单，并记下委托号。"""
        self.long_vt_orderids = self.buy(buy_price, volume, True)
        self.short_vt_orderids = self.short(short_price, volume, True)

        self.vt_orderids.extend(self.long_vt_orderids)
        self.vt_orderids.extend(self.short_vt_orderids)

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """
        停止单更新时的回调。
        """
        pass
