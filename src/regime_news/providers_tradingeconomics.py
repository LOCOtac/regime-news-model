from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

import requests

from .events_model import MacroEvent


def _get_te_api_key() -> str:
    k = os.environ.get("TRADINGECONOMICS_API_KEY", "").strip()
    if k:
        return k
    try:
        from src.secrets_local import TRADINGECONOMICS_API_KEY  # type: ignore
        return (TRADINGECONOMICS_API_KEY or "").strip()
    except Exception:
        return ""


def _parse_te_datetime(dt_str: str) -> datetime:
    """
    TradingEconomics often returns ISO-like strings (sometimes without tz).
    Treat as UTC if tz missing.
    """
    s = (dt_str or "").strip()
    if not s:
        raise ValueError("empty datetime")

    # Handle trailing Z
    s = s.replace("Z", "")

    # fromisoformat handles "YYYY-MM-DDTHH:MM:SS" and with offsets
    dt = datetime.fromisoformat(s)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


@dataclass
class TradingEconomicsConfig:
    api_key: str
    base_url: str = "https://api.tradingeconomics.com"
    timeout_s: int = 20


class TradingEconomicsClient:
    """
    Economic calendar client (TradingEconomics).

    Uses:
      GET /calendar/country/All/{start}/{end}?c=API_KEY[&importance=1|2|3]
    """

    def __init__(self, cfg: Optional[TradingEconomicsConfig] = None):
        if cfg is None:
            cfg = TradingEconomicsConfig(api_key=_get_te_api_key())
        if not cfg.api_key:
            raise RuntimeError(
                "Missing TRADINGECONOMICS_API_KEY. Set env var TRADINGECONOMICS_API_KEY or src/secrets_local.py"
            )
        self.cfg = cfg

    def get_calendar(
        self,
        start: date,
        end: date,
        importance: Optional[int] = None,
    ) -> List[MacroEvent]:
        if importance is not None and importance not in (1, 2, 3):
            raise ValueError("importance must be 1, 2, or 3")

        url = f"{self.cfg.base_url}/calendar/country/All/{start.isoformat()}/{end.isoformat()}"
        params = {"c": self.cfg.api_key}
        if importance is not None:
            params["importance"] = str(int(importance))

        r = requests.get(url, params=params, timeout=self.cfg.timeout_s)
        if r.status_code != 200:
            raise RuntimeError(f"TradingEconomics error {r.status_code}: {r.text[:300]}")
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError("TradingEconomics response not a list")

        out: List[MacroEvent] = []
        for row in data:
            try:
                dt = _parse_te_datetime(str(row.get("Date") or row.get("date") or ""))
                imp = int(row.get("Importance") or row.get("importance") or 1)
                out.append(
                    MacroEvent(
                        event=str(row.get("Event") or row.get("event") or ""),
                        country=str(row.get("Country") or row.get("country") or ""),
                        category=str(row.get("Category") or row.get("category") or ""),
                        datetime_utc=dt,
                        importance=imp if imp in (1, 2, 3) else 1,
                        actual=row.get("Actual") if "Actual" in row else row.get("actual"),
                        forecast=row.get("Forecast") if "Forecast" in row else row.get("forecast"),
                        previous=row.get("Previous") if "Previous" in row else row.get("previous"),
                        source=str(row.get("Source") or "") if row.get("Source") else None,
                        url=str(row.get("URL") or "") if row.get("URL") else None,
                    )
                )
            except Exception:
                continue

        return out
