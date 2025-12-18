from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Dict, List

import feedparser
import pandas as pd

NEG_WORDS = {"lawsuit","fraud","probe","sec","ban","recall","downgrade","miss","weak","cut","layoff","outage","breach"}
POS_WORDS = {"beat","upgrade","record","strong","raise","partnership","wins","growth","profit","surge"}

TOPICS = {
    "earnings": {"earnings","guidance","revenue","eps","margin"},
    "regulation": {"sec","doj","ftc","antitrust","ban","regulation"},
    "security": {"breach","hack","leak","ransomware","outage"},
    "macro": {"fed","rates","inflation","jobs","cpi","gdp"},
}

def fetch_google_news_rss(ticker: str, lookback_days: int = 7, max_items: int = 50) -> List[Dict]:
    url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
    d = feedparser.parse(url)
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    out = []
    for e in d.entries[:max_items]:
        published = None
        if hasattr(e, "published_parsed") and e.published_parsed:
            published = datetime(*e.published_parsed[:6])
        if published and published < cutoff:
            continue
        out.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "published_utc": published.isoformat() if published else None,
            "source": getattr(d.feed, "title", "rss"),
        })
    return out

def _score_title(title: str) -> Dict:
    t = (title or "").lower()
    tokens = set(re.findall(r"[a-z]+", t))
    neg = len(tokens & NEG_WORDS)
    pos = len(tokens & POS_WORDS)
    sentiment = pos - neg
    topic_hits = {k: int(len(tokens & v) > 0) for k, v in TOPICS.items()}
    risk_flag = int(neg >= 1 and sentiment <= 0)
    return {"sentiment": sentiment, "risk_flag": risk_flag, **topic_hits}

def score_articles(articles: List[Dict]) -> pd.DataFrame:
    rows = []
    for a in articles:
        s = _score_title(a.get("title",""))
        rows.append({**a, **s})
    return pd.DataFrame(rows)

def summarize(scored: pd.DataFrame) -> Dict:
    if scored is None or scored.empty:
        return {"news_sentiment": 0, "news_risk": 0, "topics": {}}
    news_sentiment = int(scored["sentiment"].sum())
    news_risk = int(scored["risk_flag"].sum())
    topics = {k: int(scored[k].sum()) for k in TOPICS.keys() if k in scored.columns}
    return {"news_sentiment": news_sentiment, "news_risk": news_risk, "topics": topics}
