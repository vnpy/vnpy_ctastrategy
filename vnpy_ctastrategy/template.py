"""CTA策略模板。"""

from abc import ABC, abstractmethod
from copy import copy
from typing import Any, cast
from collections.abc import Callable

from vnpy.trader.constant import Interval, Direction, Offset
from vnpy.trader.object import BarData, TickData, OrderData, TradeData

from .base import StopOrder, EngineType


class CtaTemplate(ABC):
    """CTA策略模板。"""

    author: str = ""
    parameters: list = []
    variables: list = []

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        """保存引擎、策略名和合约，复制变量列表并写入初始参数。"""
        self.cta_engine: Any = cta_engine
        self.strategy_name: str = strategy_name
        self.vt_symbol: str = vt_symbol

        self.inited: bool = False
        self.trading: bool = False
        self.pos: float = 0

        # Copy a new variables list here to avoid duplicate insert when multiple
        # strategy instances are created with the same strategy class.
        self.variables = copy(self.variables)
        self.variables.insert(0, "inited")
        self.variables.insert(1, "trading")
        self.variables.insert(2, "pos")

        self.update_setting(setting)

    def update_setting(self, setting: dict) -> None:
        """
        用配置字典中的值更新策略参数。
        """
        name: str
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    @classmethod
    def get_class_parameters(cls) -> dict:
        """
        获取策略类的默认参数字典。
        """
        class_parameters: dict = {}
        name: str
        for name in cls.parameters:
            class_parameters[name] = getattr(cls, name)
        return class_parameters

    def get_parameters(self) -> dict:
        """
        获取策略参数字典。
        """
        strategy_parameters: dict = {}
        name: str
        for name in self.parameters:
            strategy_parameters[name] = getattr(self, name)
        return strategy_parameters

    def get_variables(self) -> dict:
        """
        获取策略变量字典。
        """
        strategy_variables: dict = {}
        name: str
        for name in self.variables:
            strategy_variables[name] = getattr(self, name)
        return strategy_variables

    def get_data(self) -> dict:
        """
        获取策略数据。
        """
        strategy_data: dict = {
            "strategy_name": self.strategy_name,
            "vt_symbol": self.vt_symbol,
            "class_name": self.__class__.__name__,
            "author": self.author,
            "parameters": self.get_parameters(),
            "variables": self.get_variables(),
        }
        return strategy_data

    @abstractmethod
    def on_init(self) -> None:
        """
        策略初始化完成时的回调。
        """
        return

    def on_start(self) -> None:
        """
        策略启动时的回调。
        """
        return

    def on_stop(self) -> None:
        """
        策略停止时的回调。
        """
        return

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        return

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        return

    def on_trade(self, trade: TradeData) -> None:
        """
        新成交数据更新时的回调。
        """
        return

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        return

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """
        停止单更新时的回调。
        """
        return

    def buy(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ) -> list:
        """
        发送买入开多委托。
        """
        return self.send_order(
            Direction.LONG,
            Offset.OPEN,
            price,
            volume,
            stop,
            lock,
            net
        )

    def sell(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ) -> list:
        """
        发送卖出平多委托。
        """
        return self.send_order(
            Direction.SHORT,
            Offset.CLOSE,
            price,
            volume,
            stop,
            lock,
            net
        )

    def short(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ) -> list:
        """
        发送卖出开空委托。
        """
        return self.send_order(
            Direction.SHORT,
            Offset.OPEN,
            price,
            volume,
            stop,
            lock,
            net
        )

    def cover(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ) -> list:
        """
        发送买入平空委托。
        """
        return self.send_order(
            Direction.LONG,
            Offset.CLOSE,
            price,
            volume,
            stop,
            lock,
            net
        )

    def send_order(
        self,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ) -> list:
        """
        发送新委托。
        """
        if self.trading:
            vt_orderids: list = self.cta_engine.send_order(
                self, direction, offset, price, volume, stop, lock, net
            )
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str) -> None:
        """
        撤销已有委托。
        """
        if self.trading:
            self.cta_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """
        撤销策略发出的全部委托。
        """
        if self.trading:
            self.cta_engine.cancel_all(self)

    def write_log(self, msg: str) -> None:
        """
        写一条日志。
        """
        self.cta_engine.write_log(msg, self)

    def get_engine_type(self) -> EngineType:
        """
        返回 CTA 引擎处于回测还是实盘。
        """
        return cast(EngineType, self.cta_engine.get_engine_type())

    def get_pricetick(self) -> float:
        """
        返回交易合约的最小变动价位。
        """
        return cast(float, self.cta_engine.get_pricetick(self))

    def get_size(self) -> int:
        """
        返回交易合约的合约乘数。
        """
        return cast(int, self.cta_engine.get_size(self))

    def load_bar(
        self,
        days: int,
        interval: Interval = Interval.MINUTE,
        callback: Callable | None = None,
        use_database: bool = False
    ) -> None:
        """
        加载历史 K 线，用于初始化策略。
        """
        if not callback:
            callback = self.on_bar

        bars: list[BarData] = self.cta_engine.load_bar(
            self.vt_symbol,
            days,
            interval,
            callback,
            use_database
        )

        bar: BarData
        for bar in bars:
            callback(bar)

    def load_tick(self, days: int) -> None:
        """
        加载历史 Tick，用于初始化策略。
        """
        ticks: list[TickData] = self.cta_engine.load_tick(self.vt_symbol, days, self.on_tick)

        tick: TickData
        for tick in ticks:
            self.on_tick(tick)

    def put_event(self) -> None:
        """
        推送策略数据事件以更新界面。
        """
        if self.inited:
            self.cta_engine.put_strategy_event(self)

    def send_notification(self, msg: str) -> None:
        """
        通过全部已配置通道推送通知。
        """
        if self.inited:
            self.cta_engine.send_notification(msg, self)

    send_email: Callable[["CtaTemplate", str], None] = send_notification

    def sync_data(self) -> None:
        """
        把策略变量同步到磁盘。
        """
        if self.trading:
            self.cta_engine.sync_strategy_data(self)


class CtaSignal(ABC):
    """CTA信号模板。"""

    def __init__(self) -> None:
        """把信号持仓设为0。"""
        self.signal_pos: int = 0

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        return

    @abstractmethod
    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        return

    def set_signal_pos(self, pos: int) -> None:
        """设置信号持仓。"""
        self.signal_pos = pos

    def get_signal_pos(self) -> Any:
        """返回信号持仓。"""
        return self.signal_pos


class TargetPosTemplate(CtaTemplate):
    """按目标持仓调仓的策略模板。"""
    tick_add: int = 1

    last_tick: TickData | None = None
    last_bar: BarData | None = None
    target_pos: int = 0

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,
        setting: dict
    ) -> None:
        """初始化活动委托和撤销中的委托号，并把target_pos加入变量。"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.active_orderids: list[str] = []
        self.cancel_orderids: list[str] = []

        self.variables.append("target_pos")

    def on_tick(self, tick: TickData) -> None:
        """
        新 Tick 数据更新时的回调。
        """
        self.last_tick = tick

    def on_bar(self, bar: BarData) -> None:
        """
        新 K 线数据更新时的回调。
        """
        self.last_bar = bar

    def on_order(self, order: OrderData) -> None:
        """
        新委托数据更新时的回调。
        """
        vt_orderid: str = order.vt_orderid

        if not order.is_active():
            if vt_orderid in self.active_orderids:
                self.active_orderids.remove(vt_orderid)

            if vt_orderid in self.cancel_orderids:
                self.cancel_orderids.remove(vt_orderid)

    def check_order_finished(self) -> bool:
        """没有活动委托时返回真。"""
        if self.active_orderids:
            return False
        else:
            return True

    def set_target_pos(self, target_pos: int) -> None:
        """设置目标持仓并调仓。"""
        self.target_pos = target_pos
        self.trade()

    def trade(self) -> None:
        """有未完成委托时先撤旧单，否则按目标持仓发新单。"""
        if not self.check_order_finished():
            self.cancel_old_order()
        else:
            self.send_new_order()

    def cancel_old_order(self) -> None:
        """撤销尚未请求撤销的活动委托。"""
        vt_orderid: str
        for vt_orderid in self.active_orderids:
            if vt_orderid not in self.cancel_orderids:
                self.cancel_order(vt_orderid)
                self.cancel_orderids.append(vt_orderid)

    def send_new_order(self) -> None:
        """按持仓差额发单；回测用开仓，实盘先平后开，且已有活动委托时不再发单。"""
        pos_change: float = self.target_pos - self.pos
        if not pos_change:
            return

        long_price: float = 0
        short_price: float = 0

        if self.last_tick:
            if pos_change > 0:
                long_price = self.last_tick.ask_price_1 + self.tick_add
                if self.last_tick.limit_up:
                    long_price = min(long_price, self.last_tick.limit_up)
            else:
                short_price = self.last_tick.bid_price_1 - self.tick_add
                if self.last_tick.limit_down:
                    short_price = max(short_price, self.last_tick.limit_down)

        elif self.last_bar:
            if pos_change > 0:
                long_price = self.last_bar.close_price + self.tick_add
            else:
                short_price = self.last_bar.close_price - self.tick_add

        if self.get_engine_type() == EngineType.BACKTESTING:
            if pos_change > 0:
                vt_orderids: list[str] = self.buy(long_price, abs(pos_change))
            else:
                vt_orderids = self.short(short_price, abs(pos_change))
            self.active_orderids.extend(vt_orderids)

        else:
            if self.active_orderids:
                return

            if pos_change > 0:
                if self.pos < 0:
                    if pos_change < abs(self.pos):
                        vt_orderids = self.cover(long_price, pos_change)
                    else:
                        vt_orderids = self.cover(long_price, abs(self.pos))
                else:
                    vt_orderids = self.buy(long_price, abs(pos_change))
            else:
                if self.pos > 0:
                    if abs(pos_change) < self.pos:
                        vt_orderids = self.sell(short_price, abs(pos_change))
                    else:
                        vt_orderids = self.sell(short_price, abs(self.pos))
                else:
                    vt_orderids = self.short(short_price, abs(pos_change))
            self.active_orderids.extend(vt_orderids)
