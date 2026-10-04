from collections.abc import Iterator
from datetime import datetime
from typing import cast

import pytest

from vnpy.event import Event
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Product
from vnpy.trader.event import EVENT_TICK
from vnpy.trader.object import (
    CancelRequest,
    ContractData,
    OrderData,
    OrderRequest,
    SubscribeRequest,
    TickData,
)
from vnpy_ctastrategy.base import APP_NAME, STOPORDER_PREFIX, StopOrder, StopOrderStatus
from vnpy_ctastrategy.engine import CtaEngine
from vnpy_ctastrategy.template import CtaTemplate


class FakeGateway:
    def __init__(self) -> None:
        self.gateway_name: str = "FAKE"
        self.order_requests: list[OrderRequest] = []
        self.cancel_requests: list[CancelRequest] = []
        self.subscriptions: list[SubscribeRequest] = []
        self.orders: dict[str, OrderData] = {}
        self._count: int = 0

    def send_order(self, req: OrderRequest) -> str:
        self._count += 1
        orderid: str = str(self._count)
        order: OrderData = req.create_order_data(orderid, self.gateway_name)
        self.orders[order.vt_orderid] = order
        self.order_requests.append(req)
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        self.cancel_requests.append(req)

    def subscribe(self, req: SubscribeRequest) -> None:
        self.subscriptions.append(req)


class FakeMainEngine:
    def __init__(self, gateway: FakeGateway) -> None:
        self.gateway: FakeGateway = gateway
        self.contracts: dict[str, ContractData] = {}

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        return self.contracts.get(vt_symbol)

    def subscribe(self, req: SubscribeRequest, gateway_name: str) -> None:
        self.gateway.subscribe(req)

    def convert_order_request(
        self,
        req: OrderRequest,
        gateway_name: str,
        lock: bool,
        net: bool = False,
    ) -> list[OrderRequest]:
        return [req]

    def send_order(self, req: OrderRequest, gateway_name: str) -> str:
        return self.gateway.send_order(req)

    def update_order_request(
        self,
        req: OrderRequest,
        vt_orderid: str,
        gateway_name: str,
    ) -> None:
        return None

    def get_order(self, vt_orderid: str) -> OrderData | None:
        return self.gateway.orders.get(vt_orderid)

    def cancel_order(self, req: CancelRequest, gateway_name: str) -> None:
        self.gateway.cancel_order(req)


class FakeEventEngine:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def put(self, event: Event) -> None:
        self.events.append(event)


class MinimalStrategy(CtaTemplate):
    def __init__(
        self,
        cta_engine: object,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.init_called: bool = False
        self.start_called: bool = False
        self.stop_called: bool = False

    def on_init(self) -> None:
        self.init_called = True

    def on_start(self) -> None:
        self.start_called = True

    def on_stop(self) -> None:
        self.stop_called = True


class EngineRig:
    def __init__(
        self,
        engine: CtaEngine,
        gateway: FakeGateway,
        strategy: MinimalStrategy,
        contract: ContractData,
    ) -> None:
        self.engine: CtaEngine = engine
        self.gateway: FakeGateway = gateway
        self.strategy: MinimalStrategy = strategy
        self.contract: ContractData = contract


def make_contract() -> ContractData:
    return ContractData(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        name="rebar",
        product=Product.FUTURES,
        size=10,
        pricetick=1,
        min_volume=1,
        gateway_name="FAKE",
    )


def _disconnected_service() -> object:
    return object()


def build_engine() -> EngineRig:
    gateway: FakeGateway = FakeGateway()
    main_engine: FakeMainEngine = FakeMainEngine(gateway)
    contract: ContractData = make_contract()
    main_engine.contracts[contract.vt_symbol] = contract
    engine: CtaEngine = CtaEngine(main_engine, FakeEventEngine())  # type: ignore[arg-type]
    engine.classes[MinimalStrategy.__name__] = MinimalStrategy
    engine.add_strategy(
        MinimalStrategy.__name__,
        "minimal",
        contract.vt_symbol,
        {},
    )
    strategy: CtaTemplate = engine.strategies["minimal"]
    assert isinstance(strategy, MinimalStrategy)
    return EngineRig(engine, gateway, strategy, contract)


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> Iterator[EngineRig]:
    monkeypatch.setattr("vnpy_ctastrategy.engine.get_database", _disconnected_service)
    monkeypatch.setattr("vnpy_ctastrategy.engine.get_datafeed", _disconnected_service)
    built: EngineRig = build_engine()
    try:
        yield built
    finally:
        built.engine.init_executor.shutdown(wait=False, cancel_futures=True)


class TestCtaEngineLifecycle:
    def test_init_start_stop_sets_state_flags(self, rig: EngineRig) -> None:
        strategy: MinimalStrategy = rig.strategy
        engine: CtaEngine = rig.engine

        assert strategy.inited is False
        assert strategy.trading is False

        engine.start_strategy("minimal")
        assert strategy.trading is False
        assert strategy.start_called is False

        engine._init_strategy("minimal")
        assert strategy.init_called is True
        assert strategy.inited is True
        assert strategy.trading is False
        assert len(rig.gateway.subscriptions) == 1
        assert rig.gateway.subscriptions[0].symbol == rig.contract.symbol
        assert rig.gateway.subscriptions[0].exchange == rig.contract.exchange

        engine.start_strategy("minimal")
        assert strategy.start_called is True
        assert strategy.trading is True
        assert strategy.inited is True

        engine.stop_strategy("minimal")
        assert strategy.stop_called is True
        assert strategy.trading is False
        assert strategy.inited is True


class TestCtaEngineOrders:
    def test_send_order_and_cancel_order_reach_gateway(self, rig: EngineRig) -> None:
        strategy: MinimalStrategy = rig.strategy
        engine: CtaEngine = rig.engine
        engine._init_strategy("minimal")

        assert strategy.buy(3500, 1) == []
        assert rig.gateway.order_requests == []

        engine.start_strategy("minimal")
        vt_orderids: list[str] = strategy.buy(3500, 1)
        assert vt_orderids == ["FAKE.1"]
        assert engine.orderid_strategy_map["FAKE.1"] is strategy
        assert "FAKE.1" in engine.strategy_orderid_map["minimal"]

        req: OrderRequest = rig.gateway.order_requests[0]
        assert req.direction == Direction.LONG
        assert req.offset == Offset.OPEN
        assert req.type == OrderType.LIMIT
        assert req.symbol == rig.contract.symbol
        assert req.exchange == rig.contract.exchange
        assert req.price == 3500
        assert req.volume == 1
        assert req.reference == f"{APP_NAME}_minimal"

        recorded: OrderData = rig.gateway.orders["FAKE.1"]
        assert recorded.direction == Direction.LONG
        assert recorded.offset == Offset.OPEN

        strategy.cancel_order("FAKE.1")
        assert len(rig.gateway.cancel_requests) == 1
        cancel: CancelRequest = rig.gateway.cancel_requests[0]
        assert cancel.orderid == "1"
        assert cancel.symbol == rig.contract.symbol
        assert cancel.exchange == rig.contract.exchange

    def test_local_stop_order_when_stop_not_supported(self, rig: EngineRig) -> None:
        # 柜台不支持停止单时，buy(stop=True) 只在引擎里记 STOP 前缀单，不发给网关。
        strategy: MinimalStrategy = rig.strategy
        engine: CtaEngine = rig.engine
        rig.contract.stop_supported = False
        engine._init_strategy("minimal")
        engine.start_strategy("minimal")

        vt_orderids: list[str] = strategy.buy(3600, 1, stop=True)
        assert vt_orderids == [f"{STOPORDER_PREFIX}.1"]
        assert rig.gateway.order_requests == []
        stop_order: StopOrder = engine.stop_orders[vt_orderids[0]]
        assert stop_order.status == StopOrderStatus.WAITING
        assert stop_order.direction == Direction.LONG
        assert stop_order.offset == Offset.OPEN
        assert stop_order.price == 3600
        assert stop_order.volume == 1

    def test_local_stop_order_triggers_on_last_price(self, rig: EngineRig) -> None:
        # 实盘触发看 last_price。high 已越过但 last_price 未到时不触发。
        strategy: MinimalStrategy = rig.strategy
        engine: CtaEngine = rig.engine
        rig.contract.stop_supported = False
        engine._init_strategy("minimal")
        engine.start_strategy("minimal")

        vt_orderids: list[str] = strategy.buy(3600, 1, stop=True)
        stop_order: StopOrder = engine.stop_orders[vt_orderids[0]]
        quiet: TickData = TickData(
            symbol=rig.contract.symbol,
            exchange=rig.contract.exchange,
            datetime=datetime(2024, 1, 2, 9, 0),
            last_price=3599,
            high_price=4000,
            low_price=3000,
            gateway_name="FAKE",
        )
        engine.process_tick_event(Event(EVENT_TICK, quiet))
        assert rig.gateway.order_requests == []
        assert stop_order.status == StopOrderStatus.WAITING
        assert vt_orderids[0] in engine.stop_orders

        # high、low 都低于触发价，只有 last_price 到达才触发。
        hit: TickData = TickData(
            symbol=rig.contract.symbol,
            exchange=rig.contract.exchange,
            datetime=datetime(2024, 1, 2, 9, 1),
            last_price=3600,
            high_price=3500,
            low_price=3400,
            limit_up=3800,
            ask_price_5=3700,
            gateway_name="FAKE",
        )
        engine.process_tick_event(Event(EVENT_TICK, hit))
        assert len(rig.gateway.order_requests) == 1
        req: OrderRequest = rig.gateway.order_requests[0]
        assert req.type == OrderType.LIMIT
        assert req.direction == Direction.LONG
        assert req.offset == Offset.OPEN
        assert req.price == 3800
        assert req.volume == 1
        assert req.symbol == rig.contract.symbol
        assert stop_order.status == StopOrderStatus.TRIGGERED
        assert stop_order.vt_orderids == ["FAKE.1"]
        assert vt_orderids[0] not in engine.stop_orders

    def test_send_order_returns_empty_without_contract(self, rig: EngineRig) -> None:
        # 合约查不到时 send_order 直接返回空列表，网关收不到委托。
        strategy: MinimalStrategy = rig.strategy
        engine: CtaEngine = rig.engine
        engine._init_strategy("minimal")
        engine.start_strategy("minimal")

        main_engine: FakeMainEngine = cast(FakeMainEngine, engine.main_engine)
        main_engine.contracts.clear()
        assert main_engine.get_contract(strategy.vt_symbol) is None

        vt_orderids: list[str] = engine.send_order(
            strategy,
            Direction.LONG,
            Offset.OPEN,
            3500,
            1,
            False,
            False,
            False,
        )
        assert vt_orderids == []
        assert rig.gateway.order_requests == []
