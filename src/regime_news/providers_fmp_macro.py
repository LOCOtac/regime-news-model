from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import requests

from .events_model import MacroEvent


def _get_fmp_api_key() -> str:
    k = os.environ.get("FMP_API_KEY", "").strip()
    if k:
        return k
    try:
        from src.secrets_local import FMP_API_KEY  # type: ignore
        return (FMP_API_KEY or "").strip()
    except Exception:
        return ""


def _parse_dt_any(s: str) -> datetime:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty datetime")

    # date-only -> UTC midnight
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    s = s.replace("Z", "")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class FMPMacroCalendarConfig:
    api_key: str
    base_url: str = "https://financialmodelingprep.com/stable"
    timeout_s: int = 20


class FMPMacroCalendarClient:
    """
    FMP stable macro calendar.

    Docs endpoint:
      https://financialmodelingprep.com/stable/economic-calendar :contentReference[oaicite:1]{index=1}

    We pass from/to like other stable calendar endpoints (earnings/dividends/splits/ipos).
    If FMP ignores these params for this endpoint, it will still return data; we then filter locally.
    """

    def __init__(self, cfg: Optional[FMPMacroCalendarConfig] = None):
        if cfg is None:
            cfg = FMPMacroCalendarConfig(api_key=_get_fmp_api_key())
        if not cfg.api_key:
            raise RuntimeError("Missing FMP_API_KEY. Set env var FMP_API_KEY or src/secrets_local.py")
        self.cfg = cfg

    def _get_list(self, params: Dict[str, str]) -> List[dict]:
        url = f"{self.cfg.base_url}/economic-calendar"
        p = dict(params)
        p["apikey"] = self.cfg.api_key

        r = requests.get(url, params=p, timeout=self.cfg.timeout_s)
        if r.status_code != 200:
            raise RuntimeError(f"FMP macro calendar error {r.status_code}: {r.text[:300]}")
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError("FMP macro calendar response not a list")
        return data

    def get_calendar(self, start: date, end: date) -> List[MacroEvent]:
        # Try passing from/to (common stable calendar pattern). We also filter locally.
        rows = self._get_list({"from": start.isoformat(), "to": end.isoformat()})

        out: List[MacroEvent] = []
        start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=timezone.utc)

        for row in rows:
            try:
                # FMP macro rows commonly include fields like: date, event, country, actual/forecast/previous, etc.
                dt_raw = row.get("date") or row.get("Date") or row.get("datetime") or row.get("time")
                dt = _parse_dt_any(str(dt_raw))
                if not (start_dt <= dt <= end_dt):
                    continue

                event = str(row.get("event") or row.get("Event") or row.get("name") or "")
                country = str(row.get("country") or row.get("Country") or "")
                category = str(row.get("category") or row.get("Category") or row.get("type") or "")

                # If importance exists use it, else default 2 (medium)
                imp = row.get("importance") or row.get("Importance") or 2
                try:
                    imp_int = int(imp)
                except Exception:
                    imp_int = 2
                imp_int = 1 if imp_int < 1 else 3 if imp_int > 3 else imp_int

                out.append(
                    MacroEvent(
                        event=event,
                        country=country,
                        category=category,
                        datetime_utc=dt,
                        importance=imp_int,
                        actual=row.get("actual") if "actual" in row else row.get("Actual"),
                        forecast=row.get("forecast") if "forecast" in row else row.get("Forecast"),
                        previous=row.get("previous") if "previous" in row else row.get("Previous"),
                        source="FMP",
                        url=None,
                    )
                )
            except Exception:
                continue

        out.sort(key=lambda x: x.datetime_utc)
        return out
