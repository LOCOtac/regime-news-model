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
    n_regimes: int = 4,
    random_state: int = 7,
    market_ticker: str = "SPY",
) -> Dict[str, Any]:
    # Prices (target + market)
    px = load_prices(ticker=ticker, start=start_date, end=end_date, offline=offline)
    mkt = load_prices(ticker=market_ticker, start=start_date, end=end_date, offline=offline)

    feats, ret_1d = build_features(px, market_px=mkt)
    regime_df, gmm, scaler = fit_gmm_regimes(feats, n_regimes=n_regimes, random_state=random_state)

    # News
    try:
        articles = fetch_google_news_rss(ticker, lookback_days=7)
        scored = score_articles(articles)
        news_meta = summarize(scored)
    except Exception:
        news_meta = {"news_sentiment": 0, "news_risk": 0, "topics": {}}
        scored = pd.DataFrame()

    latest = regime_df.iloc[-1]
    current_regime = int(latest["regime"])
    q = regime_conditioned_quantiles(regime_df, ret_1d, horizons=(5, 20))

    report = {
        "ticker": ticker,
        "asof": str(regime_df.index[-1].date()),
        "regime": current_regime,
        "regime_probs": {k: float(latest[k]) for k in latest.index if k.startswith("p_regime_")},
        "expected_ranges_logret": {
            "5d": q[5].loc[current_regime].to_dict() if current_regime in q[5].index else {},
            "20d": q[20].loc[current_regime].to_dict() if current_regime in q[20].index else {},
        },
        "news": news_meta,
        "watchouts": watchouts(latest, news_meta),
        "n_rows_used": int(len(regime_df)),
    }
    return report
