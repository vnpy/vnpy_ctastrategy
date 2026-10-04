"""CTA策略实盘引擎。"""

import importlib
import traceback
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any
from collections.abc import Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from glob import glob
from concurrent.futures import Future

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine, LogEngine
from vnpy.trader.object import (
    OrderRequest,
    SubscribeRequest,
    HistoryRequest,
    CancelRequest,
    LogData,
    TickData,
    BarData,
    OrderData,
    TradeData,
    ContractData,
)
from vnpy.trader.event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE
)
from vnpy.trader.constant import (
    Direction,
    OrderType,
    Interval,
    Exchange,
    Offset,
    Status
)
from vnpy.trader.utility import load_json, save_json, extract_vt_symbol, round_to
from vnpy.trader.database import BaseDatabase, get_database, DB_TZ
from vnpy.trader.datafeed import BaseDatafeed, get_datafeed

from .base import (
    APP_NAME,
    EVENT_CTA_LOG,
    EVENT_CTA_STRATEGY,
    EVENT_CTA_STOPORDER,
    EngineType,
    StopOrder,
    StopOrderStatus,
    STOPORDER_PREFIX
)
from .template import CtaTemplate, TargetPosTemplate
from .locale import _

# 停止单状态映射
STOP_STATUS_MAP: dict[Status, StopOrderStatus] = {
    Status.SUBMITTING: StopOrderStatus.WAITING,
    Status.NOTTRADED: StopOrderStatus.WAITING,
    Status.PARTTRADED: StopOrderStatus.TRIGGERED,
    Status.ALLTRADED: StopOrderStatus.TRIGGERED,
    Status.CANCELLED: StopOrderStatus.CANCELLED,
    Status.REJECTED: StopOrderStatus.CANCELLED
}


class CtaEngine(BaseEngine):
    """CTA策略实盘引擎。"""

    engine_type: EngineType = EngineType.LIVE  # live trading engine

    setting_filename: str = "cta_strategy_setting.json"
    data_filename: str = "cta_strategy_data.json"

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """初始化策略容器、停止单计数和数据服务。"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.strategy_setting: dict = {}                                # strategy_name: dict
        self.strategy_data: dict = {}                                   # strategy_name: dict

        self.classes: dict = {}                                         # class_name: stategy_class
        self.strategies: dict = {}                                      # strategy_name: strategy

        self.symbol_strategy_map: defaultdict = defaultdict(list)       # vt_symbol: strategy list
        self.orderid_strategy_map: dict = {}                            # vt_orderid: strategy
        self.strategy_orderid_map: defaultdict = defaultdict(set)       # strategy_name: orderid set

        self.stop_order_count: int = 0                                  # for generating stop_orderid
        self.stop_orders: dict[str, StopOrder] = {}                     # stop_orderid: stop_order

        self.init_executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

        self.vt_tradeids: set = set()                                   # for filtering duplicate trade

        self.database: BaseDatabase = get_database()
        self.datafeed: BaseDatafeed = get_datafeed()

    def init_engine(self) -> None:
        """初始化数据服务、加载策略类和配置，并注册事件。"""
        self.init_datafeed()
        self.load_strategy_class()
        self.load_strategy_setting()
        self.load_strategy_data()
        self.register_event()
        self.write_log(_("CTA策略引擎初始化成功"))

    def close(self) -> None:
        """停止全部策略。"""
        self.stop_all_strategies()

    def register_event(self) -> None:
        """注册行情、委托、成交和日志事件。"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

        log_engine: LogEngine = self.main_engine.get_engine("log")  # type: ignore
        log_engine.register_log(EVENT_CTA_LOG)

    def init_datafeed(self) -> None:
        """
        初始化数据服务客户端。
        """
        result: bool = self.datafeed.init(self.write_log)
        if result:
            self.write_log(_("数据服务初始化成功"))

    def query_bar_from_datafeed(
        self, symbol: str, exchange: Exchange, interval: Interval, start: datetime, end: datetime
    ) -> list[BarData]:
        """
        从数据服务查询 K 线数据。
        """
        req: HistoryRequest = HistoryRequest(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end
        )
        data: list[BarData] = self.datafeed.query_bar_history(req, self.write_log)
        return data

    def process_tick_event(self, event: Event) -> None:
        """把Tick分发给已初始化的策略，并检查本地停止单。"""
        tick: TickData = event.data

        strategies: list = self.symbol_strategy_map[tick.vt_symbol]
        if not strategies:
            return

        self.check_stop_order(tick)

        strategy: CtaTemplate
        for strategy in strategies:
            if strategy.inited:
                self.call_strategy_func(strategy, strategy.on_tick, tick)

    def process_order_event(self, event: Event) -> None:
        """更新委托活跃状态并回调on_order；服务器停止单同时回调on_stop_order。"""
        order: OrderData = event.data

        strategy: CtaTemplate | None = self.orderid_strategy_map.get(order.vt_orderid, None)
        if not strategy:
            return

        # Remove vt_orderid if order is no longer active.
        vt_orderids: set = self.strategy_orderid_map[strategy.strategy_name]
        if order.vt_orderid in vt_orderids and not order.is_active():
            vt_orderids.remove(order.vt_orderid)

        # For server stop order, call strategy on_stop_order function
        if order.type == OrderType.STOP:
            so: StopOrder = StopOrder(
                vt_symbol=order.vt_symbol,
                direction=order.direction,      # type: ignore
                offset=order.offset,
                price=order.price,
                volume=order.volume,
                stop_orderid=order.vt_orderid,
                strategy_name=strategy.strategy_name,
                datetime=order.datetime,        # type: ignore
                status=STOP_STATUS_MAP[order.status],
                vt_orderids=[order.vt_orderid],
            )
            self.call_strategy_func(strategy, strategy.on_stop_order, so)

        # Call strategy on_order function
        self.call_strategy_func(strategy, strategy.on_order, order)

    def process_trade_event(self, event: Event) -> None:
        """过滤重复成交，更新策略持仓后回调on_trade，并同步数据和界面。"""
        trade: TradeData = event.data

        # Filter duplicate trade push
        if trade.vt_tradeid in self.vt_tradeids:
            return
        self.vt_tradeids.add(trade.vt_tradeid)

        strategy: CtaTemplate | None = self.orderid_strategy_map.get(trade.vt_orderid, None)
        if not strategy:
            return

        # Update strategy pos before calling on_trade method
        if trade.direction == Direction.LONG:
            strategy.pos += trade.volume
        else:
            strategy.pos -= trade.volume

        self.call_strategy_func(strategy, strategy.on_trade, trade)

        # Sync strategy variables to data file
        self.sync_strategy_data(strategy)

        # Update GUI
        self.put_strategy_event(strategy)

    def check_stop_order(self, tick: TickData) -> None:
        """用最新价触发本地停止单，触发后发送限价单。"""
        stop_order: StopOrder
        for stop_order in list(self.stop_orders.values()):
            if stop_order.vt_symbol != tick.vt_symbol:
                continue

            long_triggered: bool = (
                stop_order.direction == Direction.LONG and tick.last_price >= stop_order.price
            )
            short_triggered: bool = (
                stop_order.direction == Direction.SHORT and tick.last_price <= stop_order.price
            )

            if long_triggered or short_triggered:
                strategy: CtaTemplate = self.strategies[stop_order.strategy_name]

                # To get excuted immediately after stop order is
                # triggered, use limit price if available, otherwise
                # use ask_price_5 or bid_price_5
                if stop_order.direction == Direction.LONG:
                    if tick.limit_up:
                        price: float = tick.limit_up
                    else:
                        price = tick.ask_price_5
                else:
                    if tick.limit_down:
                        price = tick.limit_down
                    else:
                        price = tick.bid_price_5

                contract: ContractData | None = self.main_engine.get_contract(stop_order.vt_symbol)
                if not contract:
                    continue

                vt_orderids: list = self.send_limit_order(
                    strategy,
                    contract,
                    stop_order.direction,
                    stop_order.offset,
                    price,
                    stop_order.volume,
                    stop_order.lock,
                    stop_order.net
                )

                # Update stop order status if placed successfully
                if vt_orderids:
                    # Remove from relation map.
                    self.stop_orders.pop(stop_order.stop_orderid)

                    strategy_vt_orderids: set = self.strategy_orderid_map[strategy.strategy_name]
                    if stop_order.stop_orderid in strategy_vt_orderids:
                        strategy_vt_orderids.remove(stop_order.stop_orderid)

                    # Change stop order status to cancelled and update to strategy.
                    stop_order.status = StopOrderStatus.TRIGGERED
                    stop_order.vt_orderids = vt_orderids

                    self.call_strategy_func(
                        strategy, strategy.on_stop_order, stop_order
                    )
                    self.put_stop_order_event(stop_order)

    def send_server_order(
        self,
        strategy: CtaTemplate,
        contract: ContractData,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        type: OrderType,
        lock: bool,
        net: bool
    ) -> list:
        """
        向服务器发送新委托。
        """
        # Create request and send order.
        original_req: OrderRequest = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            offset=offset,
            type=type,
            price=price,
            volume=volume,
            reference=f"{APP_NAME}_{strategy.strategy_name}"
        )

        # Convert with offset converter
        req_list: list[OrderRequest] = self.main_engine.convert_order_request(
            original_req,
            contract.gateway_name,
            lock,
            net
        )

        # Send Orders
        vt_orderids: list = []

        req: OrderRequest
        for req in req_list:
            vt_orderid: str = self.main_engine.send_order(req, contract.gateway_name)

            # Check if sending order successful
            if not vt_orderid:
                continue

            vt_orderids.append(vt_orderid)

            self.main_engine.update_order_request(req, vt_orderid, contract.gateway_name)

            # Save relationship between orderid and strategy.
            self.orderid_strategy_map[vt_orderid] = strategy
            self.strategy_orderid_map[strategy.strategy_name].add(vt_orderid)

        return vt_orderids

    def send_limit_order(
        self,
        strategy: CtaTemplate,
        contract: ContractData,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        lock: bool,
        net: bool
    ) -> list:
        """
        向服务器发送限价单。
        """
        return self.send_server_order(
            strategy,
            contract,
            direction,
            offset,
            price,
            volume,
            OrderType.LIMIT,
            lock,
            net
        )

    def send_server_stop_order(
        self,
        strategy: CtaTemplate,
        contract: ContractData,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        lock: bool,
        net: bool
    ) -> list:
        """
        向服务器发送停止单。

        仅当交易服务器支持停止单时使用。
        """
        return self.send_server_order(
            strategy,
            contract,
            direction,
            offset,
            price,
            volume,
            OrderType.STOP,
            lock,
            net
        )

    def send_local_stop_order(
        self,
        strategy: CtaTemplate,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        lock: bool,
        net: bool
    ) -> list:
        """
        创建本地停止单。
        """
        self.stop_order_count += 1
        stop_orderid: str = f"{STOPORDER_PREFIX}.{self.stop_order_count}"

        stop_order: StopOrder = StopOrder(
            vt_symbol=strategy.vt_symbol,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            stop_orderid=stop_orderid,
            strategy_name=strategy.strategy_name,
            datetime=datetime.now(DB_TZ),
            lock=lock,
            net=net
        )

        self.stop_orders[stop_orderid] = stop_order

        vt_orderids: set = self.strategy_orderid_map[strategy.strategy_name]
        vt_orderids.add(stop_orderid)

        self.call_strategy_func(strategy, strategy.on_stop_order, stop_order)
        self.put_stop_order_event(stop_order)

        return [stop_orderid]

    def cancel_server_order(self, strategy: CtaTemplate, vt_orderid: str) -> None:
        """
        按 vt_orderid 撤销已有委托。
        """
        order: OrderData | None = self.main_engine.get_order(vt_orderid)
        if not order:
            self.write_log(_("撤单失败，找不到委托{}").format(vt_orderid), strategy)
            return

        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def cancel_local_stop_order(self, strategy: CtaTemplate, stop_orderid: str) -> None:
        """
        撤销本地停止单。
        """
        stop_order: StopOrder | None = self.stop_orders.get(stop_orderid, None)
        if not stop_order:
            return
        strategy = self.strategies[stop_order.strategy_name]

        # Remove from relation map.
        self.stop_orders.pop(stop_orderid)

        vt_orderids: set = self.strategy_orderid_map[strategy.strategy_name]
        if stop_orderid in vt_orderids:
            vt_orderids.remove(stop_orderid)

        # Change stop order status to cancelled and update to strategy.
        stop_order.status = StopOrderStatus.CANCELLED

        self.call_strategy_func(strategy, strategy.on_stop_order, stop_order)
        self.put_stop_order_event(stop_order)

    def send_order(
        self,
        strategy: CtaTemplate,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool,
        lock: bool,
        net: bool
    ) -> list:
        """按合约最小变动取整后发送委托；停止单在柜台支持时走服务器，否则在本地生成。"""
        contract: ContractData | None = self.main_engine.get_contract(strategy.vt_symbol)
        if not contract:
            self.write_log(_("委托失败，找不到合约：{}").format(strategy.vt_symbol), strategy)
            return []

        # Round order price and volume to nearest incremental value
        price = round_to(price, contract.pricetick)
        volume = round_to(volume, contract.min_volume)

        if stop:
            if contract.stop_supported:
                return self.send_server_stop_order(
                    strategy, contract, direction, offset, price, volume, lock, net
                )
            else:
                return self.send_local_stop_order(
                    strategy, direction, offset, price, volume, lock, net
                )
        else:
            return self.send_limit_order(
                strategy, contract, direction, offset, price, volume, lock, net
            )

    def cancel_order(self, strategy: CtaTemplate, vt_orderid: str) -> None:
        """停止单号走本地撤单，其余走服务器撤单。"""
        if vt_orderid.startswith(STOPORDER_PREFIX):
            self.cancel_local_stop_order(strategy, vt_orderid)
        else:
            self.cancel_server_order(strategy, vt_orderid)

    def cancel_all(self, strategy: CtaTemplate) -> None:
        """
        撤销策略的全部活动委托。
        """
        vt_orderids: set = self.strategy_orderid_map[strategy.strategy_name]
        if not vt_orderids:
            return

        vt_orderid: str
        for vt_orderid in copy(vt_orderids):
            self.cancel_order(strategy, vt_orderid)

    def get_engine_type(self) -> EngineType:
        """返回引擎类型。"""
        return self.engine_type

    def get_pricetick(self, strategy: CtaTemplate) -> float | None:
        """
        返回合约最小变动价位。
        """
        contract: ContractData | None = self.main_engine.get_contract(strategy.vt_symbol)

        if contract:
            return contract.pricetick
        else:
            return None

    def get_size(self, strategy: CtaTemplate) -> int | None:
        """
        返回合约乘数。
        """
        contract: ContractData | None = self.main_engine.get_contract(strategy.vt_symbol)

        if contract:
            return contract.size       # type: ignore
        else:
            return None

    def load_bar(
        self,
        vt_symbol: str,
        days: int,
        interval: Interval,
        callback: Callable[[BarData], None],
        use_database: bool
    ) -> list[BarData]:
        """加载指定天数的历史K线；use_database为真时只查数据库，否则先查接口或数据服务，没有数据再查数据库。"""
        symbol: str
        exchange: Exchange
        symbol, exchange = extract_vt_symbol(vt_symbol)
        end: datetime = datetime.now(DB_TZ)
        start: datetime = end - timedelta(days)
        bars: list[BarData] = []

        # Pass gateway and datafeed if use_database set to True
        if not use_database:
            # Query bars from gateway if available
            contract: ContractData | None = self.main_engine.get_contract(vt_symbol)

            if contract and contract.history_data:
                req: HistoryRequest = HistoryRequest(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    start=start,
                    end=end
                )
                bars = self.main_engine.query_history(req, contract.gateway_name)

            # Try to query bars from datafeed, if not found, load from database.
            else:
                bars = self.query_bar_from_datafeed(symbol, exchange, interval, start, end)

        if not bars:
            bars = self.database.load_bar_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start=start,
                end=end,
            )

        return bars

    def load_tick(
        self,
        vt_symbol: str,
        days: int,
        callback: Callable[[TickData], None]
    ) -> list[TickData]:
        """从数据库加载指定天数的历史Tick。"""
        symbol: str
        exchange: Exchange
        symbol, exchange = extract_vt_symbol(vt_symbol)
        end: datetime = datetime.now(DB_TZ)
        start: datetime = end - timedelta(days)

        ticks: list[TickData] = self.database.load_tick_data(
            symbol=symbol,
            exchange=exchange,
            start=start,
            end=end,
        )

        return ticks

    def call_strategy_func(
        self, strategy: CtaTemplate, func: Callable, params: Any = None
    ) -> None:
        """
        调用策略函数并捕获抛出的异常。
        """
        try:
            if params:
                func(params)
            else:
                func()
        except Exception:
            strategy.trading = False
            strategy.inited = False

            msg: str = _("触发异常已停止\n{}").format(traceback.format_exc())
            self.write_log(msg, strategy)

    def add_strategy(
        self, class_name: str, strategy_name: str, vt_symbol: str, setting: dict
    ) -> None:
        """
        添加一个新策略。
        """
        if strategy_name in self.strategies:
            self.write_log(_("创建策略失败，存在重名{}").format(strategy_name))
            return

        strategy_class: type[CtaTemplate] | None = self.classes.get(class_name, None)
        if not strategy_class:
            self.write_log(_("创建策略失败，找不到策略类{}").format(class_name))
            return

        if "." not in vt_symbol:
            self.write_log(_("创建策略失败，本地代码缺失交易所后缀"))
            return

        exchange_str: str
        __, exchange_str = vt_symbol.split(".")
        if exchange_str not in Exchange.__members__:
            self.write_log(_("创建策略失败，本地代码的交易所后缀不正确"))
            return

        strategy: CtaTemplate = strategy_class(self, strategy_name, vt_symbol, setting)
        self.strategies[strategy_name] = strategy

        # Add vt_symbol to strategy map.
        strategies: list = self.symbol_strategy_map[vt_symbol]
        strategies.append(strategy)

        # Update to setting file.
        self.update_strategy_setting(strategy_name, setting)

        self.put_strategy_event(strategy)

    def init_strategy(self, strategy_name: str) -> Future:
        """
        初始化策略。
        """
        return self.init_executor.submit(self._init_strategy, strategy_name)

    def _init_strategy(self, strategy_name: str) -> None:
        """
        初始化队列中的策略。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]

        if strategy.inited:
            self.write_log(_("{}已经完成初始化，禁止重复操作").format(strategy_name))
            return

        self.write_log(_("{}开始执行初始化").format(strategy_name))

        # Call on_init function of strategy
        self.call_strategy_func(strategy, strategy.on_init)

        # Restore strategy data(variables)
        data: dict | None = self.strategy_data.get(strategy_name, None)
        if data:
            name: str
            for name in strategy.variables:
                value: object | None = data.get(name, None)
                if value is not None:
                    setattr(strategy, name, value)

        # Subscribe market data
        contract: ContractData | None = self.main_engine.get_contract(strategy.vt_symbol)
        if contract:
            req: SubscribeRequest = SubscribeRequest(
                symbol=contract.symbol, exchange=contract.exchange)
            self.main_engine.subscribe(req, contract.gateway_name)
        else:
            self.write_log(_("行情订阅失败，找不到合约{}").format(strategy.vt_symbol), strategy)

        # Put event to update init completed status.
        strategy.inited = True
        self.put_strategy_event(strategy)
        self.write_log(_("{}初始化完成").format(strategy_name))

    def start_strategy(self, strategy_name: str) -> None:
        """
        启动策略。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]
        if not strategy.inited:
            self.write_log(_("策略{}启动失败，请先初始化").format(strategy.strategy_name))
            return

        if strategy.trading:
            self.write_log(_("{}已经启动，请勿重复操作").format(strategy_name))
            return

        self.call_strategy_func(strategy, strategy.on_start)
        strategy.trading = True

        self.put_strategy_event(strategy)

    def stop_strategy(self, strategy_name: str) -> None:
        """
        停止策略。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]
        if not strategy.trading:
            return

        # Call on_stop function of the strategy
        self.call_strategy_func(strategy, strategy.on_stop)

        # Change trading status of strategy to False
        strategy.trading = False

        # Cancel all orders of the strategy
        self.cancel_all(strategy)

        # Sync strategy variables to data file
        self.sync_strategy_data(strategy)

        # Update GUI
        self.put_strategy_event(strategy)

    def edit_strategy(self, strategy_name: str, setting: dict) -> None:
        """
        修改策略参数。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]
        strategy.update_setting(setting)

        self.update_strategy_setting(strategy_name, setting)
        self.put_strategy_event(strategy)

    def remove_strategy(self, strategy_name: str) -> bool:
        """
        移除策略。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]
        if strategy.trading:
            self.write_log(_("策略{}移除失败，请先停止").format(strategy.strategy_name))
            return False

        # Remove setting
        self.remove_strategy_setting(strategy_name)

        # Remove from symbol strategy map
        strategies: list = self.symbol_strategy_map[strategy.vt_symbol]
        strategies.remove(strategy)

        # Remove from active orderid map
        if strategy_name in self.strategy_orderid_map:
            vt_orderids: set = self.strategy_orderid_map.pop(strategy_name)

            # Remove vt_orderid strategy map
            vt_orderid: str
            for vt_orderid in vt_orderids:
                if vt_orderid in self.orderid_strategy_map:
                    self.orderid_strategy_map.pop(vt_orderid)

        # Remove from strategies
        self.strategies.pop(strategy_name)

        self.write_log(_("策略{}移除成功").format(strategy.strategy_name))
        return True

    def load_strategy_class(self) -> None:
        """
        从源代码加载策略类。
        """
        path1: Path = Path(__file__).parent.joinpath("strategies")
        self.load_strategy_class_from_folder(path1, "vnpy_ctastrategy.strategies")

        path2: Path = Path.cwd().joinpath("strategies")
        self.load_strategy_class_from_folder(path2, "strategies")

    def load_strategy_class_from_folder(self, path: Path, module_name: str = "") -> None:
        """
        从指定目录加载策略类。
        """
        suffix: str
        for suffix in ["py", "pyd", "so"]:
            pathname: str = str(path.joinpath(f"*.{suffix}"))
            filepath: str
            for filepath in glob(pathname):
                filename: str = Path(filepath).stem
                name: str = f"{module_name}.{filename}"
                self.load_strategy_class_from_module(name)

    def load_strategy_class_from_module(self, module_name: str) -> None:
        """
        从模块文件加载策略类。
        """
        try:
            module: ModuleType = importlib.import_module(module_name)

            # 重载模块，确保如果策略文件中有任何修改，能够立即生效。
            importlib.reload(module)

            name: str
            for name in dir(module):
                value: object = getattr(module, name)
                if (
                    isinstance(value, type)
                    and issubclass(value, CtaTemplate)
                    and value not in {CtaTemplate, TargetPosTemplate}
                ):
                    self.classes[value.__name__] = value
        except:  # noqa
            msg: str = _("策略文件{}加载失败，触发异常：\n{}").format(module_name, traceback.format_exc())
            self.write_log(msg)

    def load_strategy_data(self) -> None:
        """
        从 JSON 文件加载策略数据。
        """
        self.strategy_data = load_json(self.data_filename)

    def sync_strategy_data(self, strategy: CtaTemplate) -> None:
        """
        把策略数据同步到 JSON 文件。
        """
        data: dict = strategy.get_variables()
        data.pop("inited")      # Strategy status (inited, trading) should not be synced.
        data.pop("trading")

        self.strategy_data[strategy.strategy_name] = data
        save_json(self.data_filename, self.strategy_data)

    def get_all_strategy_class_names(self) -> list:
        """
        返回已加载策略类的名称。
        """
        return list(self.classes.keys())

    def get_strategy_class_parameters(self, class_name: str) -> dict:
        """
        获取策略类的默认参数。
        """
        strategy_class: type[CtaTemplate] = self.classes[class_name]

        parameters: dict = {}
        name: str
        for name in strategy_class.parameters:
            parameters[name] = getattr(strategy_class, name)

        return parameters

    def get_strategy_parameters(self, strategy_name: str) -> dict:
        """
        获取策略参数。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]
        return strategy.get_parameters()

    def init_all_strategies(self) -> dict[str, Future]:
        """提交全部策略的初始化任务。"""
        futures: dict[str, Future] = {}
        strategy_name: str
        for strategy_name in self.strategies.keys():
            futures[strategy_name] = self.init_strategy(strategy_name)
        return futures

    def start_all_strategies(self) -> None:
        """启动全部策略。"""
        strategy_name: str
        for strategy_name in self.strategies.keys():
            self.start_strategy(strategy_name)

    def stop_all_strategies(self) -> None:
        """停止全部策略。"""
        strategy_name: str
        for strategy_name in self.strategies.keys():
            self.stop_strategy(strategy_name)

    def load_strategy_setting(self) -> None:
        """
        加载配置文件。
        """
        self.strategy_setting = load_json(self.setting_filename)

        strategy_name: str
        strategy_config: dict
        for strategy_name, strategy_config in self.strategy_setting.items():
            self.add_strategy(
                strategy_config["class_name"],
                strategy_name,
                strategy_config["vt_symbol"],
                strategy_config["setting"]
            )

    def update_strategy_setting(self, strategy_name: str, setting: dict) -> None:
        """
        更新配置文件。
        """
        strategy: CtaTemplate = self.strategies[strategy_name]

        self.strategy_setting[strategy_name] = {
            "class_name": strategy.__class__.__name__,
            "vt_symbol": strategy.vt_symbol,
            "setting": setting,
        }
        save_json(self.setting_filename, self.strategy_setting)

    def remove_strategy_setting(self, strategy_name: str) -> None:
        """
        从配置文件中移除策略。
        """
        if strategy_name not in self.strategy_setting:
            return

        self.strategy_setting.pop(strategy_name)
        save_json(self.setting_filename, self.strategy_setting)

        self.strategy_data.pop(strategy_name, None)
        save_json(self.data_filename, self.strategy_data)

    def put_stop_order_event(self, stop_order: StopOrder) -> None:
        """
        推送事件以更新停止单状态。
        """
        event: Event = Event(EVENT_CTA_STOPORDER, stop_order)
        self.event_engine.put(event)

    def put_strategy_event(self, strategy: CtaTemplate) -> None:
        """
        推送事件以更新策略状态。
        """
        data: dict = strategy.get_data()
        event: Event = Event(EVENT_CTA_STRATEGY, data)
        self.event_engine.put(event)

    def write_log(self, msg: str, strategy: CtaTemplate | None = None) -> None:
        """
        创建 CTA 引擎日志事件。
        """
        if strategy:
            msg = f"[{strategy.strategy_name}]  {msg}"

        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(type=EVENT_CTA_LOG, data=log)
        self.event_engine.put(event)

    def send_notification(self, msg: str, strategy: CtaTemplate | None = None) -> None:
        """
        通过全部已配置通道推送通知。
        """
        if strategy:
            subject: str = f"{strategy.strategy_name}"
        else:
            subject = _("CTA策略引擎")

        self.main_engine.send_notification(msg, subject)
