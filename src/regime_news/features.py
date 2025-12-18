from __future__ import annotations
import numpy as np
import pandas as pd

def rolling_drawdown(px: pd.Series, window: int = 252) -> pd.Series:
    roll_max = px.rolling(window).max()
    return (px / roll_max) - 1.0

def build_features(px: pd.DataFrame, market_px: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.Series]:
    """px: columns date,ticker,adj_close,volume for target ticker.
    market_px optional same format for SPY to include market return feature.
    Returns (features_df indexed by date, daily_log_return_series aligned)
    """
    df = px.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df = df.set_index("date")

    close = df["adj_close"].astype(float)
    ret = np.log(close).diff().rename("ret_1d")

    feats = pd.DataFrame(index=df.index)
    feats["ret_1d"] = ret
    feats["vol_20d"] = ret.rolling(20).std() * np.sqrt(252)
    feats["vol_60d"] = ret.rolling(60).std() * np.sqrt(252)
    feats["mom_20d"] = ret.rolling(20).sum()
    feats["mom_60d"] = ret.rolling(60).sum()
    feats["dd_252d"] = rolling_drawdown(close, 252)

    if market_px is not None and len(market_px) > 0:
        m = market_px.copy()
        m["date"] = pd.to_datetime(m["date"])
        m = m.sort_values("date").set_index("date")
        mret = np.log(m["adj_close"].astype(float)).diff().rename("mkt_ret_1d")
        feats = feats.join(mret, how="left")

    feats = feats.replace([np.inf, -np.inf], np.nan).dropna()
    return feats, ret.loc[feats.index]
