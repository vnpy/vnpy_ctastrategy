"""海龟信号策略。"""

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    Direction,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class TurtleSignalStrategy(CtaTemplate):
    """用唐奇安通道分批开仓，并用ATR或出场通道平仓的策略。"""
    author = "用Python的交易员"

    entry_window: int = 20
    exit_window: int = 10
    atr_window: int = 20
    fixed_size: int = 1

    entry_up: float = 0
    entry_down: float = 0
    exit_up: float = 0
    exit_down: float = 0
    atr_value: float = 0
    long_entry: float = 0
    short_entry: float = 0
    long_stop: float = 0
    short_stop: float = 0

    parameters = ["entry_window", "exit_window", "atr_window", "fixed_size"]
    variables = ["entry_up", "entry_down", "exit_up", "exit_down", "atr_value"]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.bg: BarGenerator = BarGenerator(self.on_bar)
        self.am: ArrayManager = ArrayManager()

        self.load_bar(20)

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

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # Only calculates new entry channel when no position holding
        if not self.pos:
            self.entry_up, self.entry_down = self.am.donchian(
                self.entry_window
            )

        self.exit_up, self.exit_down = self.am.donchian(self.exit_window)

        if not self.pos:
            self.atr_value = self.am.atr(self.atr_window)

            self.long_entry = 0
            self.short_entry = 0
            self.long_stop = 0
            self.short_stop = 0

            self.send_buy_orders(self.entry_up)
            self.send_short_orders(self.entry_down)
        elif self.pos > 0:
            self.send_buy_orders(self.entry_up)

            sell_price: float = max(self.long_stop, self.exit_down)
            self.sell(sell_price, abs(self.pos), True)

        elif self.pos < 0:
            self.send_short_orders(self.entry_down)

            cover_price: float = min(self.short_stop, self.exit_up)
            self.cover(cover_price, abs(self.pos), True)

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        """
        新成交数据更新时的回调。
        """
        if trade.direction == Direction.LONG:
            self.long_entry = trade.price
            self.long_stop = self.long_entry - 2 * self.atr_value
        else:
            self.short_entry = trade.price
            self.short_stop = self.short_entry + 2 * self.atr_value

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """
        停止单更新时的回调。
        """
        pass

    def send_buy_orders(self, price: float) -> None:
        """按当前持仓单位，在价格上方分批发出最多四笔买入停止单。"""
        t: float = self.pos / self.fixed_size

        if t < 1:
            self.buy(price, self.fixed_size, True)

        if t < 2:
            self.buy(price + self.atr_value * 0.5, self.fixed_size, True)

        if t < 3:
            self.buy(price + self.atr_value, self.fixed_size, True)

        if t < 4:
            self.buy(price + self.atr_value * 1.5, self.fixed_size, True)

    def send_short_orders(self, price: float) -> None:
        """按当前持仓单位，在价格下方分批发出最多四笔卖出停止单。"""
        t: float = self.pos / self.fixed_size

        if t > -1:
            self.short(price, self.fixed_size, True)

        if t > -2:
            self.short(price - self.atr_value * 0.5, self.fixed_size, True)

        if t > -3:
            self.short(price - self.atr_value, self.fixed_size, True)

        if t > -4:
            self.short(price - self.atr_value * 1.5, self.fixed_size, True)
