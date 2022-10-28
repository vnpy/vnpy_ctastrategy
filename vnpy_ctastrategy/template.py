""""""
from abc import ABC
from copy import copy
from typing import Any, Callable, Dict
from collections import defaultdict

from vnpy.trader.constant import Interval, Direction, Offset
from vnpy.trader.object import BarData, TickData, OrderData, TradeData
from vnpy.trader.utility import virtual


from .base import StopOrder, EngineType


class CtaTemplate(ABC):
    """"""

    author = ""
    parameters = []
    variables = []

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ):
        """"""
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol

        self.inited = False
        self.trading = False
        self.pos = 0

        # Copy a new variables list here to avoid duplicate insert when multiple
        # strategy instances are created with the same strategy class.
        self.variables = copy(self.variables)
        self.variables.insert(0, "inited")
        self.variables.insert(1, "trading")
        self.variables.insert(2, "pos")

        self.update_setting(setting)

    def update_setting(self, setting: dict):
        """
        Update strategy parameter wtih value in setting dict.
        """
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    @classmethod
    def get_class_parameters(cls):
        """
        Get default parameters dict of strategy class.
        """
        class_parameters = {}
        for name in cls.parameters:
            class_parameters[name] = getattr(cls, name)
        return class_parameters

    def get_parameters(self):
        """
        Get strategy parameters dict.
        """
        strategy_parameters = {}
        for name in self.parameters:
            strategy_parameters[name] = getattr(self, name)
        return strategy_parameters

    def get_variables(self):
        """
        Get strategy variables dict.
        """
        strategy_variables = {}
        for name in self.variables:
            strategy_variables[name] = getattr(self, name)
        return strategy_variables

    def get_data(self):
        """
        Get strategy data.
        """
        strategy_data = {
            "strategy_name": self.strategy_name,
            "vt_symbol": self.vt_symbol,
            "class_name": self.__class__.__name__,
            "author": self.author,
            "parameters": self.get_parameters(),
            "variables": self.get_variables(),
        }
        return strategy_data

    @virtual
    def on_init(self):
        """
        Callback when strategy is inited.
        """
        pass

    @virtual
    def on_start(self):
        """
        Callback when strategy is started.
        """
        pass

    @virtual
    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        pass

    @virtual
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        pass

    @virtual
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        pass

    @virtual
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        pass

    @virtual
    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    @virtual
    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def buy(
        self,
        limit_price: float,
        volume: float,
        signal_price: float = None,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ):
        """
        Send buy order to open a long position.
        """
        return self.send_order(
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=limit_price,
            volume=volume,
            signal_price=signal_price,
            stop=stop,
            lock=lock,
            net=net
        )

    def sell(
        self,
        limit_price: float,
        volume: float,
        signal_price: float = None,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ):
        """
        Send sell order to close a long position.
        """
        return self.send_order(
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=limit_price,
            volume=volume,
            signal_price=signal_price,
            stop=stop,
            lock=lock,
            net=net
        )

    def short(
        self,
        limit_price: float,
        volume: float,
        signal_price: float = None,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ):
        """
        Send short order to open as short position.
        """
        return self.send_order(
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=limit_price,
            volume=volume,
            signal_price=signal_price,
            stop=stop,
            lock=lock,
            net=net
        )

    def cover(
        self,
        limit_price: float,
        volume: float,
        signal_price: float = None,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ):
        """
        Send cover order to close a short position.
        """
        return self.send_order(
            direction=Direction.LONG,
            offset=Offset.CLOSE,
            price=limit_price,
            volume=volume,
            signal_price=signal_price,
            stop=stop,
            lock=lock,
            net=net
        )

    def send_order(
        self,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        signal_price: float = None,
        stop: bool = False,
        lock: bool = False,
        net: bool = False
    ):
        """
        Send a new order.
        """
        if signal_price is None:
            signal_price = price
        if self.trading:
            vt_orderids = self.cta_engine.send_order(self,
                                                     direction=direction,
                                                     offset=offset,
                                                     price=price,
                                                     volume=volume,
                                                     stop=stop,
                                                     lock=lock,
                                                     net=net,
                                                     signal_price=signal_price)
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str):
        """
        Cancel an existing order.
        """
        if self.trading:
            self.cta_engine.cancel_order(self, vt_orderid)

    def cancel_all(self):
        """
        Cancel all orders sent by strategy.
        """
        if self.trading:
            self.cta_engine.cancel_all(self)

    def write_log(self, msg: str):
        """
        Write a log message.
        """
        self.cta_engine.write_log(msg, self)

    def get_engine_type(self):
        """
        Return whether the cta_engine is backtesting or live trading.
        """
        return self.cta_engine.get_engine_type()

    def get_pricetick(self):
        """
        Return pricetick data of trading contract.
        """
        return self.cta_engine.get_pricetick(self)

    def load_bar(
        self,
        days: int,
        interval: Interval = Interval.MINUTE,
        callback: Callable = None,
        use_database: bool = False
    ):
        """
        Load historical bar data for initializing strategy.
        """
        if not callback:
            callback = self.on_bar

        self.cta_engine.load_bar(
            self.vt_symbol,
            days,
            interval,
            callback,
            use_database
        )

    def load_tick(self, days: int):
        """
        Load historical tick data for initializing strategy.
        """
        self.cta_engine.load_tick(self.vt_symbol, days, self.on_tick)

    def put_event(self):
        """
        Put an strategy data event for ui update.
        """
        if self.inited:
            self.cta_engine.put_strategy_event(self)

    def send_email(self, msg):
        """
        Send email to default receiver.
        """
        if self.inited:
            self.cta_engine.send_email(msg, self)

    def sync_data(self):
        """
        Sync strategy variables value into disk storage.
        """
        if self.trading:
            self.cta_engine.sync_strategy_data(self)

    def get_moment_profit(self, etf_symbol: str):
        """
        获取ETF折、溢价瞬时利润
        折价： 买ETF，赎回成篮子，卖篮子
        溢价： 买篮子，申购成ETF，卖ETF
        :param etf_symbol:
        :return:
        """
        return self.cta_engine.main_engine.get_moment_profit(etf_symbol)

    def get_spread(self, spread_name):
        return self.cta_engine.main_engine.get_spread(spread_name)


class CtaSignal(ABC):
    """"""

    variables = []          # 本信号中需要记录、持久化保存，初始化完成后加载的参数
    parameters = []

    def __init__(self, target_pos_template=None):
        """

        :param target_pos_template:
        """
        self.signal_pos = 0
        self.target_pos_template: TargetPosTemplate = target_pos_template

    @virtual
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        pass

    @virtual
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        pass

    def set_signal_pos(self, pos):
        """
        :param pos:
        :return:
        """
        self.signal_pos = pos

    def get_signal_pos(self):
        """"""
        return self.signal_pos

    def write_log(self, msg: str):
        self.target_pos_template.write_log(msg=msg)


class TargetPosTemplate(CtaTemplate):
    """"""
    tick_add = 1
    TB_add = 0.005          # 国债

    last_tick = None
    last_bar = None
    target_pos = 0
    parameters = []
    variables = ['last_order_time', 'pos', 'signal_pos', 'target_pos']

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.active_orderids = []
        self.cancel_orderids = []

        self.variables.append("target_pos")
        self.signal_dict: Dict[str, CtaSignal] = {}
        self.signal_pos: Dict[str, int] = {}

    def get_variables(self):
        # 获取TargetPos的参数
        var_dict = super(TargetPosTemplate, self).get_variables()
        # 获取signal的参数
        for k, v in self.signal_dict.items():
            var_dict[k] = {vk: getattr(v, vk) for vk in v.variables}
        return var_dict

    def get_parameters(self):
        # 获取TargetPos的参数
        var_dict = super(TargetPosTemplate, self).get_parameters()
        # 获取signal的参数
        for k, v in self.signal_dict.items():
            var_dict[k] = {vk: getattr(v, vk) for vk in v.parameters}
        return var_dict

    @virtual
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.last_tick = tick

        if self.trading:
            self.trade()

    @virtual
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.last_bar = bar

    @virtual
    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        vt_orderid = order.vt_orderid

        if not order.is_active():
            if vt_orderid in self.active_orderids:
                self.active_orderids.remove(vt_orderid)

            if vt_orderid in self.cancel_orderids:
                self.cancel_orderids.remove(vt_orderid)

    def check_order_finished(self):
        """"""
        if self.active_orderids:
            return False
        else:
            return True

    def calculate_target_pos(self):
        """
        计算目标持仓
        :return:
        """
        target_pos = 0
        for k, v in self.signal_dict.items():
            self.signal_pos[k] = v.get_signal_pos()
            target_pos += self.signal_pos[k]
        return self.set_target_pos(target_pos)

    def set_target_pos(self, target_pos):
        """"""
        pos_change_flag = False
        if target_pos != self.pos or target_pos != self.target_pos:
            self.target_pos = target_pos
            self.trade()
            if self.last_tick:
                self.last_order_time = self.last_tick.datetime.strftime('%Y-%m-%d %H:%M:%S')
                signal_price = self.last_tick.last_price
            else:
                signal_price = self.last_bar.close_price
                self.last_order_time = self.last_bar.datetime.strftime('%Y-%m-%d %H:%M:%S')
            pos_change_flag = True
            self.write_log(f'[{self.last_order_time}] pos change: {self.pos} --> {self.target_pos} | signal_price {signal_price}')
        self.put_event()
        # self.write_log('初始化过程中禁止下单!')
        return pos_change_flag

    def trade(self):
        """"""
        if not self.check_order_finished():
            self.cancel_old_order()
        else:
            self.send_new_order()

    def cancel_old_order(self):
        """"""
        for vt_orderid in self.active_orderids:
            if vt_orderid not in self.cancel_orderids:
                self.cancel_order(vt_orderid)
                self.cancel_orderids.append(vt_orderid)

    def send_new_order(self):
        """"""
        pos_change = self.target_pos - self.pos
        if not pos_change:
            return

        long_price = 0
        short_price = 0

        if self.last_tick:
            tick_add = self.TB_add if self.last_tick.symbol.startswith('T') else self.tick_add
            signal_price = self.last_tick.last_price
            if pos_change > 0:
                long_price = self.last_tick.ask_price_1 + tick_add
                if self.last_tick.limit_up:
                    long_price = min(long_price, self.last_tick.limit_up)
            else:
                short_price = self.last_tick.bid_price_1 - tick_add
                if self.last_tick.limit_down:
                    short_price = max(short_price, self.last_tick.limit_down)

        else:
            tick_add = self.TB_add if self.last_bar.symbol.startswith('T') else self.tick_add
            signal_price = self.last_bar.close_price
            if pos_change > 0:
                long_price = self.last_bar.close_price + tick_add
            else:
                short_price = self.last_bar.close_price - tick_add

        if self.get_engine_type() == EngineType.BACKTESTING:
            if pos_change > 0:
                vt_orderids = self.buy(long_price, abs(pos_change), signal_price=signal_price)
            else:
                vt_orderids = self.short(short_price, abs(pos_change), signal_price=signal_price)
            self.active_orderids.extend(vt_orderids)

        else:
            if self.active_orderids:
                return

            if pos_change > 0:
                if self.pos < 0:
                    if pos_change < abs(self.pos):
                        vt_orderids = self.cover(long_price, pos_change, signal_price=signal_price)
                    else:
                        vt_orderids = self.cover(long_price, abs(self.pos), signal_price=signal_price)
                else:
                    vt_orderids = self.buy(long_price, abs(pos_change), signal_price=signal_price)
            else:
                if self.pos > 0:
                    if abs(pos_change) < self.pos:
                        vt_orderids = self.sell(short_price, abs(pos_change), signal_price=signal_price)
                    else:
                        vt_orderids = self.sell(short_price, abs(self.pos), signal_price=signal_price)
                else:
                    vt_orderids = self.short(short_price, abs(pos_change), signal_price=signal_price)
            self.active_orderids.extend(vt_orderids)
