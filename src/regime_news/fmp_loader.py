from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

STABLE_EOD_FULL = "https://financialmodelingprep.com/stable/historical-price-eod/full"

@dataclass
class FmpLoaderConfig:
    api_key: str
    cache_dir: str = "data/cache/prices"

def _get_api_key() -> str:
    k = os.environ.get("FMP_API_KEY", "").strip()
    if k:
        return k
    try:
        from src.secrets_local import FMP_API_KEY  # type: ignore
        return (FMP_API_KEY or "").strip()
    except Exception:
        return ""

def _cache_path(cache_dir: str, ticker: str) -> Path:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    return Path(cache_dir) / f"{ticker.upper()}_eod.pkl"

def load_prices(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    use_cache: bool = True,
    offline: bool = False,
    cfg: Optional[FmpLoaderConfig] = None,
) -> pd.DataFrame:
    """Return columns: date, ticker, adj_close, volume (daily EOD).
    Cache format: pandas pickle (NO CSV).
    """
    ticker = ticker.upper().strip()
    cfg = cfg or FmpLoaderConfig(api_key=_get_api_key())

    cache_file = _cache_path(cfg.cache_dir, ticker)
    cached = None
    if use_cache and cache_file.exists():
        try:
            cached = pd.read_pickle(cache_file)
        except Exception:
            cached = None

    if offline:
        if cached is None:
            raise RuntimeError(f"Offline mode but no cache found at {cache_file}")
        return cached

    if not cfg.api_key:
        if cached is not None:
            return cached
        raise RuntimeError("Missing FMP_API_KEY. Set env var FMP_API_KEY or src/secrets_local.py")

    params = {"symbol": ticker, "apikey": cfg.api_key}
    if start:
        params["from"] = start
    if end:
        params["to"] = end

    r = requests.get(STABLE_EOD_FULL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError(f"No price data returned for {ticker}.")

    df = pd.DataFrame(data)
    df.columns = [c.strip().lower() for c in df.columns]

    # Normalize
    if "date" not in df.columns:
        raise RuntimeError("Unexpected response: missing 'date'")

    # FMP sometimes uses 'adjClose'/'adjclose'
    if "adjclose" in df.columns and "adj_close" not in df.columns:
        df = df.rename(columns={"adjclose": "adj_close"})
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]

    if "volume" not in df.columns:
        df["volume"] = 0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "adj_close"]).copy()
    df["ticker"] = ticker
    df = df.sort_values("date")
    out = df[["date", "ticker", "adj_close", "volume"]].reset_index(drop=True)

    if use_cache:
        out.to_pickle(cache_file)

    return out
