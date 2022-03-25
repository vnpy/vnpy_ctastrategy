"""
Defines constants and objects used in CtaStrategy App.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict

from vnpy.trader.constant import Direction, Offset, Interval

APP_NAME: str = "CtaStrategy"
STOPORDER_PREFIX: str = "STOP"


class StopOrderStatus(Enum):
    WAITING: str = "等待中"
    CANCELLED: str = "已撤销"
    TRIGGERED: str = "已触发"


class EngineType(Enum):
    LIVE: str = "实盘"
    BACKTESTING: str = "回测"


class BacktestingMode(Enum):
    BAR: int = 1
    TICK: int = 2


@dataclass
class StopOrder:
    vt_symbol: str
    direction: Direction
    offset: Offset
    price: float
    volume: float
    stop_orderid: str
    strategy_name: str
    datetime: datetime
    lock: bool = False
    net: bool = False
    vt_orderids: list = field(default_factory=list)
    status: StopOrderStatus = StopOrderStatus.WAITING


EVENT_CTA_LOG: str = "eCtaLog"
EVENT_CTA_STRATEGY: str = "eCtaStrategy"
EVENT_CTA_STOPORDER: str = "eCtaStopOrder"

INTERVAL_DELTA_MAP: Dict[Interval, timedelta] = {
    Interval.TICK: timedelta(milliseconds=1),
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}
