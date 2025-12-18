from __future__ import annotations
import pandas as pd

def forward_log_return(ret_1d: pd.Series, horizon: int) -> pd.Series:
    return ret_1d.shift(-1).rolling(horizon).sum().shift(-(horizon - 1))

def regime_conditioned_quantiles(regime_df: pd.DataFrame, ret_1d: pd.Series, horizons=(5, 20)) -> dict:
    out = {}
    for h in horizons:
        fwd = forward_log_return(ret_1d, h)
        tmp = regime_df[["regime"]].copy()
        tmp[f"fwd_{h}d"] = fwd
        tmp = tmp.dropna()
        qs = tmp.groupby("regime")[f"fwd_{h}d"].quantile([0.05, 0.50, 0.95]).unstack()
        out[h] = qs.rename(columns={0.05:"q05",0.50:"q50",0.95:"q95"})
    return out

def watchouts(latest_row: pd.Series, news_meta: dict) -> list[str]:
    flags = []
    p_cols = [c for c in latest_row.index if c.startswith("p_regime_")]
    if p_cols:
        if float(latest_row[p_cols].max()) < 0.60:
            flags.append("Regime uncertainty rising (probabilities are mixed).")
    if "vol_20d" in latest_row and "vol_60d" in latest_row:
        if float(latest_row["vol_20d"]) > float(latest_row["vol_60d"]) * 1.15:
            flags.append("Short-term volatility is spiking vs medium-term baseline.")
    if "dd_252d" in latest_row and float(latest_row["dd_252d"]) < -0.20:
        flags.append("In a deep drawdown zone (higher fragility / headline sensitivity).")

    if news_meta.get("news_risk", 0) >= 2:
        flags.append("Multiple risk headlines recently (watch for gap risk / IV expansion).")

    topics = news_meta.get("topics", {}) or {}
    for k, v in topics.items():
        if v >= 2:
            flags.append(f"News topic cluster: {k} (increased event risk).")
    return flags
