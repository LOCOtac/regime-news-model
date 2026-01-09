from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class RegimeState:
    """
    Policy-facing regime state (what your risk governor consumes).
    regime_id is optional and can retain your numeric GMM label.
    """
    regime_name: str  # risk_on | late_cycle | risk_off | transition
    confidence: float  # 0..1
    regime_id: Optional[int] = None


@dataclass(frozen=True)
class MacroEvent:
    """
    Normalized TradingEconomics calendar event.
    """
    event: str
    country: str
    category: str
    datetime_utc: datetime
    importance: int  # 1..3
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    source: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class CompanyEvent:
    """
    Normalized FMP stable calendar event.
    """
    symbol: str
    event_type: str  # earnings | dividends | splits | ipo
    datetime_utc: datetime
    meta: dict


@dataclass(frozen=True)
class EventOverlayDecision:
    allow_new_positions: bool
    risk_multiplier: float
    tighten_stops: bool
    notes: str
