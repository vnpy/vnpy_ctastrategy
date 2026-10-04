"""
定义 CTA 策略应用使用的常量和对象。
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from vnpy.trader.constant import Direction, Offset, Interval
from .locale import _

APP_NAME: str = "CtaStrategy"
STOPORDER_PREFIX: str = "STOP"


class StopOrderStatus(Enum):
    """停止单状态。"""
    WAITING = _("等待中")
    CANCELLED = _("已撤销")
    TRIGGERED = _("已触发")


class EngineType(Enum):
    """引擎类型，区分实盘和回测。"""
    LIVE = _("实盘")
    BACKTESTING = _("回测")


class BacktestingMode(Enum):
    """回测数据模式，分为K线和Tick。"""
    BAR = 1
    TICK = 2


@dataclass
class StopOrder:
    """停止单数据。"""
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


INTERVAL_DELTA_MAP: dict[Interval, timedelta] = {
    Interval.TICK: timedelta(milliseconds=1),
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}
