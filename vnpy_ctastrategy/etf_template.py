# -*- coding:utf-8 -*-
"""
@FileName  :etf_template.py
@Time      :2022/10/26 13:48
@Author    :fsksf

对策略模板进行改造，使其支持多标的买卖、持仓，篮子，申赎
"""
from abc import ABC
from copy import copy
from typing import Any, Callable, Dict
import collections
from vnpy_ctastrategy.template import CtaTemplate
from vnpy.trader.constant import Interval, Direction, Offset, OrderType
from vnpy.trader.object import BarData, TickData, OrderData, TradeData


class ETFTemplate(CtaTemplate):

    author = 'kangyuqiang'

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,         # 篮子对应的ETF
        setting: dict,
    ):
        """"""
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol

        self.inited = False
        self.trading = False
        self.pos = collections.defaultdict(lambda: 0)
        self.target_basket_pos = 0  # 篮子目标数量
        self.require_basket_pos = {}  # 篮子成分股每个股票还需要买多少
        self.basket_pos = 0 # 篮子包数量（成分股折算）
        self.etf_pos = 0 # etf的数量

        self.variables = copy(self.variables)
        self.variables.insert(0, "inited")
        self.variables.insert(1, "trading")
        self.variables.insert(2, "etf_pos")
        self.variables.insert(3, "basket_pos")
        self.variables.insert(4, "pos")

        self.update_setting(setting)

    def on_trade(self, trade: TradeData):
        self.etf_pos = self.pos[self.vt_symbol]
        self.calc_basket_pos()

    def calc_basket_pos(self):
        """计算持仓"""
        self.require_basket_pos = {}
        contract = self.cta_engine.main_engine.get_contract(self.vt_symbol)
        target_basket_pos = self.target_basket_pos
        basket_pos = float('inf')
        for comp in self.cta_engine.main_engine.get_basket_components(self.vt_symbol):
            # 只买卖同市场
            if comp.exchange != contract.exchange:
                continue
            share = comp.share
            if share == 0:
                continue

            # 处理涨跌停
            cash_flag = comp.cash_flag()
            if cash_flag == 2:
                continue
            elif cash_flag == 1:
                tick = self.cta_engine.main_engine.get_tick(comp.vt_symbol)
                if tick and tick.last_price == tick.limit_up or tick.last_price == tick.limit_down:
                    self.write_log(f'{tick.vt_symbol} 涨停或者跌停，up: {tick.limit_up}, down {tick.limit_down} '
                                   f'last price {tick.last_price}')
                    continue

            comp_current_pos = self.pos[comp.vt_symbol]
            # 篮子合成持仓，取小
            _basket_pos = comp_current_pos / share
            if _basket_pos < basket_pos:
                basket_pos = _basket_pos

            comp_target_pos = share * target_basket_pos
            comp_require_pos = comp_target_pos - comp_current_pos
            if comp_require_pos != 0:
                self.require_basket_pos[comp.vt_symbol] = comp_require_pos
        self.basket_pos = basket_pos
        self.etf_pos = self.pos[self.vt_symbol]

    def purchase(self, volume):
        """
        申购
        """
        return self.send_order(price=0, volume=volume, direction=Direction.PURCHASE, offset=Offset.NONE,
                               lock=False)

    def redemption(self, volume):
        """
        赎回
        """
        return self.send_order(price=0, volume=volume, direction=Direction.REDEMPTION, offset=Offset.NONE,
                               lock=False)

    def set_basket_target(self, target_volume):
        """
        买卖篮子设置篮子目标仓位，系统会根据目标仓位进行计算买卖逻辑. 如果是卖出，应该设置target_volume=0
        :param target_volume:
        :return:
        """
        self.target_basket_pos = target_volume
        self.calc_basket_pos()
        for k, v in self.require_basket_pos.items():
            if v > 0:
                self.cta_engine.send_order(
                    strategy=self,
                    direction=Direction.LONG,
                    offset=Offset.OPEN,
                    price=0,
                    volume=v,
                    stop=False,
                    lock=False,
                    net=False,
                    signal_price=None,
                    vt_symbol=k,
                    type=OrderType.JG_TDC_PRICETYPE_BestOrLimit)
            elif v < 0:
                self.cta_engine.send_order(
                    strategy=self,
                    direction=Direction.SHORT,
                    offset=Offset.CLOSE,
                    price=0,
                    volume=abs(v),
                    stop=False,
                    lock=False,
                    net=False,
                    signal_price=None,
                    vt_symbol=k,
                    type=OrderType.JG_TDC_PRICETYPE_BestOrLimit)