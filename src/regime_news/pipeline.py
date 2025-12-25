from __future__ import annotations

from typing import Dict, Any, Optional
import pandas as pd

from .fmp_loader import load_prices
from .features import build_features
from .regime import fit_gmm_regimes
from .news import fetch_google_news_rss, score_articles, summarize
from .fusion import regime_conditioned_quantiles, watchouts


def run_pipeline(
    ticker: str,
    start_date: str = "2015-01-01",
    end_date: Optional[str] = None,
    offline: bool = False,
    n_regimes: int = 3,
    random_state: int = 7,
    market_ticker: str = "SPY",
) -> Dict[str, Any]:
    """
    Regime + News pipeline.

    Training/production guardrails:
      - Restrict n_regimes to 2 or 3 during early training (prevents overfitting).
      - Emit debug output so callers can verify the value is threaded correctly.
      - Basic data sanity checks to avoid silent failures.
      - Provide regime diagnostics (counts, min regime size) for stability monitoring.
    """

    # --- Guardrails / Debug ---
    print(f"[DEBUG] run_pipeline ticker={ticker} n_regimes={n_regimes} offline={offline} "
          f"start={start_date} end={end_date} market={market_ticker}")

    if n_regimes not in (2, 3):
        raise ValueError("n_regimes must be 2 or 3 during training (set --n_regimes 2 or 3).")

    # --- Load prices (target + market) ---
    px = load_prices(ticker=ticker, start=start_date, end=end_date, offline=offline)
    mkt = load_prices(ticker=market_ticker, start=start_date, end=end_date, offline=offline)

    # Basic sanity: ensure we have enough data
    if px is None or len(px) < 60:
        raise ValueError(f"Not enough price data for {ticker}. Need >= 60 rows, got {0 if px is None else len(px)}.")
    if mkt is None or len(mkt) < 60:
        raise ValueError(f"Not enough price data for market_ticker={market_ticker}. Need >= 60 rows, got {0 if mkt is None else len(mkt)}.")

    # --- Build features ---
    feats, ret_1d = build_features(px, market_px=mkt)

    if feats is None or len(feats) < 60:
        raise ValueError(f"Not enough feature rows for {ticker}. Need >= 60, got {0 if feats is None else len(feats)}.")

    # Drop all-NaN columns defensively (helps avoid HMM/GMM blowing up silently)
    feats = feats.copy()
    feats = feats.dropna(axis=1, how="all")

    # If after feature engineering we have too many NaNs, clean lightly
    # (Prefer minimal intervention to avoid distorting signal)
    nan_frac = float(feats.isna().mean().mean()) if feats.size else 1.0
    if nan_frac > 0.20:
        # Light cleaning: forward/back fill then drop remaining NaNs
        feats = feats.ffill().bfill().dropna()
        ret_1d = ret_1d.loc[feats.index].dropna()

    # Align ret_1d to feats index
    ret_1d = ret_1d.loc[feats.index].dropna()
    feats = feats.loc[ret_1d.index]

    if len(feats) < 60:
        raise ValueError(f"After cleaning/alignment, not enough rows to fit regimes. Got {len(feats)} rows.")

    # --- Fit regimes ---
    regime_df, gmm, scaler = fit_gmm_regimes(
        feats,
        n_regimes=n_regimes,
        random_state=random_state,
    )

    if regime_df is None or len(regime_df) == 0:
        raise ValueError("Regime fitting returned empty output.")

    # --- Regime diagnostics ---
    # Expect a "regime" column; counts help you see if a regime is degenerate (tiny)
    if "regime" not in regime_df.columns:
        raise ValueError("regime_df missing required column: 'regime'")

    regime_counts = regime_df["regime"].value_counts().sort_index()
    min_regime_size = int(regime_counts.min()) if len(regime_counts) else 0

    # Simple warning threshold: each regime should have at least ~5% of samples
    # If not, it's likely degenerate / unstable.
    warning = None
    if len(regime_df) > 0:
        frac_min = min_regime_size / len(regime_df)
        if frac_min < 0.05:
            warning = (
                f"Regime imbalance detected: smallest regime has {min_regime_size} / {len(regime_df)} "
                f"rows ({frac_min:.1%}). Consider using fewer regimes or adjusting features."
            )

    # --- News ---
    try:
        articles = fetch_google_news_rss(ticker, lookback_days=7)
        scored = score_articles(articles)
        news_meta = summarize(scored)
    except Exception as e:
        news_meta = {
            "news_sentiment": 0,
            "news_risk": 0,
            "topics": {},
            "error": str(e),
        }
        scored = pd.DataFrame()

    # --- Outputs ---
    latest = regime_df.iloc[-1]
    current_regime = int(latest["regime"])

    q = regime_conditioned_quantiles(regime_df, ret_1d, horizons=(5, 20))

    report: Dict[str, Any] = {
        # Existing keys (keep stable)
        "ticker": ticker,
        "asof": str(regime_df.index[-1].date()),
        "regime": current_regime,
        "regime_probs": {k: float(latest[k]) for k in latest.index if str(k).startswith("p_regime_")},
        "expected_ranges_logret": {
            "5d": q[5].loc[current_regime].to_dict() if 5 in q and current_regime in q[5].index else {},
            "20d": q[20].loc[current_regime].to_dict() if 20 in q and current_regime in q[20].index else {},
        },
        "news": news_meta,
        "watchouts": watchouts(latest, news_meta),
        "n_rows_used": int(len(regime_df)),

        # New diagnostics (safe additions)
        "n_regimes_used": int(n_regimes),
        "regime_counts": {int(k): int(v) for k, v in regime_counts.to_dict().items()},
        "min_regime_size": int(min_regime_size),
        "warning": warning,
    }

    return report
