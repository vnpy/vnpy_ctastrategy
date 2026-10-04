from collections.abc import Iterator

import pytest

from vnpy.event import Event
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Product
from vnpy.trader.object import (
    CancelRequest,
    ContractData,
    OrderData,
    OrderRequest,
    SubscribeRequest,
)
from vnpy_ctastrategy.base import APP_NAME
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
