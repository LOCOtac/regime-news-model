from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence

import requests

from .events_model import CompanyEvent


def _get_fmp_api_key() -> str:
    k = os.environ.get("FMP_API_KEY", "").strip()
    if k:
        return k
    try:
        from src.secrets_local import FMP_API_KEY  # type: ignore
        return (FMP_API_KEY or "").strip()
    except Exception:
        return ""


def _parse_fmp_date_any(s: str) -> datetime:
    """
    FMP stable calendar endpoints often provide date-only strings YYYY-MM-DD.
    Treat date-only as UTC midnight.
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date")

    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # Try ISO-ish
    s = s.replace("Z", "")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class FMPStableEventsConfig:
    api_key: str
    base_url: str = "https://financialmodelingprep.com/stable"
    timeout_s: int = 20


class FMPStableEventsClient:
    """
    FMP STABLE calendar endpoints ONLY (no /api/v3):

      /stable/earnings-calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=...
      /stable/dividends-calendar?from=...&to=...
      /stable/splits-calendar?from=...&to=...
      /stable/ipos-calendar?from=...&to=...
    """

    def __init__(self, cfg: Optional[FMPStableEventsConfig] = None):
        if cfg is None:
            cfg = FMPStableEventsConfig(api_key=_get_fmp_api_key())
        if not cfg.api_key:
            raise RuntimeError("Missing FMP_API_KEY. Set env var FMP_API_KEY or src/secrets_local.py")
        self.cfg = cfg

    def _get_list(self, path: str, params: Dict[str, str]) -> List[dict]:
        url = f"{self.cfg.base_url}{path}"
        p = dict(params)
        p["apikey"] = self.cfg.api_key

        r = requests.get(url, params=p, timeout=self.cfg.timeout_s)
        if r.status_code != 200:
            raise RuntimeError(f"FMP error {r.status_code}: {r.text[:300]}")
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError("FMP response not a list")
        return data

    def earnings(self, start: date, end: date, symbols: Optional[Sequence[str]] = None) -> List[CompanyEvent]:
        rows = self._get_list("/earnings-calendar", {"from": start.isoformat(), "to": end.isoformat()})
        return self._normalize(rows, "earnings", symbols, date_keys=("date", "earningsDate", "reportedDate"))

    def dividends(self, start: date, end: date, symbols: Optional[Sequence[str]] = None) -> List[CompanyEvent]:
        rows = self._get_list("/dividends-calendar", {"from": start.isoformat(), "to": end.isoformat()})
        return self._normalize(rows, "dividends", symbols, date_keys=("date", "paymentDate", "recordDate", "declarationDate"))

    def splits(self, start: date, end: date, symbols: Optional[Sequence[str]] = None) -> List[CompanyEvent]:
        rows = self._get_list("/splits-calendar", {"from": start.isoformat(), "to": end.isoformat()})
        return self._normalize(rows, "splits", symbols, date_keys=("date", "splitDate"))

    def ipos(self, start: date, end: date) -> List[CompanyEvent]:
        rows = self._get_list("/ipos-calendar", {"from": start.isoformat(), "to": end.isoformat()})
        out: List[CompanyEvent] = []
        for row in rows:
            dt = None
            for k in ("date", "ipoDate"):
                if row.get(k):
                    try:
                        dt = _parse_fmp_date_any(str(row.get(k)))
                        break
                    except Exception:
                        continue
            if dt is None:
                continue
            sym = str(row.get("symbol") or row.get("ticker") or "IPO").upper().strip()
            out.append(CompanyEvent(symbol=sym or "IPO", event_type="ipo", datetime_utc=dt, meta=row))
        return out

    def _normalize(
        self,
        rows: List[dict],
        event_type: str,
        symbols: Optional[Sequence[str]],
        date_keys: Sequence[str],
    ) -> List[CompanyEvent]:
        symset = None
        if symbols:
            symset = {s.upper().strip() for s in symbols if s and s.strip()}

        out: List[CompanyEvent] = []
        for row in rows:
            sym = str(row.get("symbol") or "").upper().strip()
            if symset is not None and sym not in symset:
                continue

            dt = None
            for k in date_keys:
                if row.get(k):
                    try:
                        dt = _parse_fmp_date_any(str(row.get(k)))
                        break
                    except Exception:
                        continue
            if dt is None:
                continue

            out.append(CompanyEvent(symbol=sym, event_type=event_type, datetime_utc=dt, meta=row))
        return out
