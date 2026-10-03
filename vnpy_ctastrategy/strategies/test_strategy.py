"""委托测试策略。"""

from collections.abc import Callable
from time import time

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData
)


class TestStrategy(CtaTemplate):
    """依次测试市价单、限价单、全部撤单和停止单的策略。"""
    author = "用Python的交易员"

    test_trigger: int = 10

    tick_count: int = 0
    test_all_done: bool = False

    parameters = ["test_trigger"]
    variables = ["tick_count", "test_all_done"]

    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        self.write_log("策略初始化")

        self.test_funcs: list[Callable[[], None]] = [
            self.test_market_order,
            self.test_limit_order,
            self.test_cancel_all,
            self.test_stop_order
        ]

        self.last_tick: TickData | None = None

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
        if self.test_all_done:
            return

        self.last_tick = tick

        self.tick_count += 1
        if self.tick_count >= self.test_trigger:
            self.tick_count = 0

            if self.test_funcs:
                test_func: Callable[[], None] = self.test_funcs.pop(0)

                start: float = time()
                test_func()
                time_cost: float = (time() - start) * 1000
                self.write_log(f"耗时{time_cost}毫秒")
            else:
                self.write_log("测试已全部完成")
                self.test_all_done = True

        self.put_event()

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        pass

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        """
        新成交数据更新时的回调。
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """
        停止单更新时的回调。
        """
        self.put_event()

    def test_market_order(self) -> None:
        """用涨停价买入1手，没有最新Tick时只记日志。"""
        if not self.last_tick:
            self.write_log("没有最新tick数据")
            return

        self.buy(self.last_tick.limit_up, 1)
        self.write_log("执行市价单测试")

    def test_limit_order(self) -> None:
        """用跌停价买入1手，没有最新Tick时只记日志。"""
        if not self.last_tick:
            self.write_log("没有最新tick数据")
            return

        self.buy(self.last_tick.limit_down, 1)
        self.write_log("执行限价单测试")

    def test_stop_order(self) -> None:
        """用卖一价发出买入停止单，没有最新Tick时只记日志。"""
        if not self.last_tick:
            self.write_log("没有最新tick数据")
            return

        self.buy(self.last_tick.ask_price_1, 1, True)
        self.write_log("执行停止单测试")

    def test_cancel_all(self) -> None:
        """撤销全部委托。"""
        self.cancel_all()
        self.write_log("执行全部撤单测试")
