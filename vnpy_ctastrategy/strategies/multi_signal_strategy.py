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
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, rsi_window: int, rsi_level: float):
        """Constructor"""
        super().__init__(target_pos_template)

        self.rsi_window = rsi_window
        self.rsi_level = rsi_level
        self.rsi_long = 50 + self.rsi_level
        self.rsi_short = 50 - self.rsi_level

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        rsi_value = self.am.rsi(self.rsi_window)

        if rsi_value >= self.rsi_long:
            self.set_signal_pos(1)
        elif rsi_value <= self.rsi_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class Rsi15Signal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, rsi_15window: int, rsi_15level: float):
        """Constructor"""
        super().__init__(target_pos_template)
        self.rsi_window = rsi_15window
        self.rsi_level = rsi_15level
        self.rsi_long = 50 + self.rsi_level
        self.rsi_short = 50 - self.rsi_level

        self.bg = BarGenerator(self.on_bar, window=15, on_window_bar=self.on_15bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_15bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        if self.target_pos_template.trading:
            # 实盘过程中
            pass
        else:
            # 正在初始化
            pass

        rsi_value = self.am.rsi(self.rsi_window)

        if rsi_value >= self.rsi_long:
            self.set_signal_pos(1)
        elif rsi_value <= self.rsi_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class Rsi30Signal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, rsi_30window: int, rsi_30level: float):
        """Constructor"""
        super().__init__(target_pos_template)
        self.rsi_window = rsi_30window
        self.rsi_level = rsi_30level
        self.rsi_long = 50 + self.rsi_level
        self.rsi_short = 50 - self.rsi_level

        self.bg = BarGenerator(self.on_bar, window=30, on_window_bar=self.on_30bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_30bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        rsi_value = self.am.rsi(self.rsi_window)

        if rsi_value >= self.rsi_long:
            self.set_signal_pos(1)
        elif rsi_value <= self.rsi_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class CciSignal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, cci_window: int, cci_level: float):
        """"""
        super().__init__(target_pos_template)
        self.cci_window = cci_window
        self.cci_level = cci_level
        self.cci_long = self.cci_level
        self.cci_short = -self.cci_level

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        cci_value = self.am.cci(self.cci_window)

        if cci_value >= self.cci_long:
            self.set_signal_pos(1)
        elif cci_value <= self.cci_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class Cci15Signal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, cci_15window: int, cci_15level: float):
        """"""
        super().__init__(target_pos_template)
        self.cci_window = cci_15window
        self.cci_level = cci_15level
        self.cci_long = self.cci_level
        self.cci_short = -self.cci_level

        self.bg = BarGenerator(self.on_bar, window=15, on_window_bar=self.on_15bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_15bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        cci_value = self.am.cci(self.cci_window)

        if cci_value >= self.cci_long:
            self.set_signal_pos(1)
        elif cci_value <= self.cci_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class Cci30Signal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, cci_30window: int, cci_30level: float):
        """"""
        super().__init__(target_pos_template)

        self.cci_window = cci_30window
        self.cci_level = cci_30level
        self.cci_long = self.cci_level
        self.cci_short = -self.cci_level

        self.bg = BarGenerator(self.on_bar, window=30, on_window_bar=self.on_30bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_30bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        cci_value = self.am.cci(self.cci_window)

        if cci_value >= self.cci_long:
            self.set_signal_pos(1)
        elif cci_value <= self.cci_short:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class MaSignal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, fast_window: int, slow_window: int):
        """"""
        super().__init__(target_pos_template)
        self.fast_window = fast_window
        self.slow_window = slow_window

        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """"""
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        fast_ma = self.am.sma(self.fast_window)
        slow_ma = self.am.sma(self.slow_window)

        if fast_ma > slow_ma:
            self.set_signal_pos(1)
        elif fast_ma < slow_ma:
            self.set_signal_pos(-1)
        else:
            self.set_signal_pos(0)


class Ma15Signal(CtaSignal):
    """"""
    variables = ['signal_price']
    signal_price = 0

    def __init__(self, target_pos_template: TargetPosTemplate, fast_15window: int, slow_15window: int):
        """"""
        super().__init__(target_pos_template)
        self.fast_window = fast_15window
        self.slow_window = slow_15window

        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_15min_bar(self, bar: BarData):
        """"""
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        fast_ma = self.am.sma(self.fast_window)
        slow_ma = self.am.sma(self.slow_window)

        if fast_ma > slow_ma:
            if self.set_signal_pos(1):
                self.signal_price = bar.close_price
        elif fast_ma < slow_ma:
            if self.set_signal_pos(-1):
                self.signal_price = bar.close_price
        else:
            if self.set_signal_pos(0):
                self.signal_price = bar.close_price


class Ma30Signal(CtaSignal):
    """"""

    def __init__(self, target_pos_template: TargetPosTemplate, fast_30window: int, slow_30window: int):
        """"""
        super().__init__(target_pos_template)
        self.fast_window = fast_30window
        self.slow_window = slow_30window

        self.bg = BarGenerator(self.on_bar, 30, self.on_30min_bar)
        self.am = ArrayManager()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_30min_bar(self, bar: BarData):
        """"""
        self.am.update_bar(bar)
        if not self.am.inited:
            self.set_signal_pos(0)

        fast_ma = self.am.sma(self.fast_window)
        slow_ma = self.am.sma(self.slow_window)

        if fast_ma > slow_ma:
            self.set_signal_pos(1)

        elif fast_ma < slow_ma:
            self.set_signal_pos(-1)

        else:
            self.set_signal_pos(0)


class MultiSignalStrategy(TargetPosTemplate):
    """"""

    author = "用Python的交易员"

    rsi_window = 14
    rsi_15window = 14
    rsi_30window = 14
    rsi_level = 20
    rsi_15level = 20
    rsi_30level = 20
    cci_window = 30
    cci_15window = 30
    cci_30window = 30
    cci_level = 10
    cci_15level = 10
    cci_30level = 10
    fast_window = 5
    slow_window = 20
    fast_15window = 2
    fast_30window = 2
    slow_15window = 4
    slow_30window = 4

    signal_pos = {}
    last_order_time = 0

    parameters = ["rsi_window", "rsi_level", "cci_window",
                  "cci_level", "fast_window", "slow_window"]
    variables = ["signal_pos", "target_pos", "last_order_time"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(on_bar=self.on_bar)

        self.signal_dict['rsi'] = RsiSignal(rsi_window=self.rsi_window, rsi_level=self.rsi_level, target_pos_template=self)
        self.signal_dict['rsi15'] = Rsi15Signal(rsi_15window=self.rsi_15window, rsi_15level=self.rsi_15level, target_pos_template=self)
        self.signal_dict['rsi30'] = Rsi30Signal(rsi_30window=self.rsi_30window, rsi_30level=self.rsi_30level, target_pos_template=self)
        self.signal_dict['cci'] = CciSignal(cci_window=self.cci_window, cci_level=self.cci_level, target_pos_template=self)
        self.signal_dict['cci15'] = Cci15Signal(cci_15window=self.cci_15window, cci_15level=self.cci_15level, target_pos_template=self)
        self.signal_dict['cci30'] = Cci30Signal(cci_30window=self.cci_30window, cci_30level=self.cci_30level, target_pos_template=self)
        self.signal_dict['ma'] = MaSignal(fast_window=self.fast_window, slow_window=self.slow_window, target_pos_template=self)
        self.signal_dict['ma15'] = Ma15Signal(fast_15window=self.fast_15window, slow_15window=self.slow_15window, target_pos_template=self)
        self.signal_dict['ma30'] = Ma30Signal(fast_30window=self.fast_30window, slow_30window=self.slow_30window, target_pos_template=self)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(100)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        策略信号都是用的1minute数据，所以在总的策略中一次生成分钟数据，然后每个signal直接使用分钟数据
        """
        super(MultiSignalStrategy, self).on_tick(tick)
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        super(MultiSignalStrategy, self).on_bar(bar)
        for k, v in self.signal_dict.items():
            v.on_bar(bar)
        self.calculate_target_pos()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        super(MultiSignalStrategy, self).on_order(order)

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
