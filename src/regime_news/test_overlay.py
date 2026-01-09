from src.regime_news.pipeline import run_pipeline
from src.regime_news.overlay_runner import add_event_overlay_to_report

r = run_pipeline("AAPL", start_date="2015-01-01", n_regimes=3, offline=False)
r2 = add_event_overlay_to_report(
    r,
    portfolio_symbols=["AAPL", "MSFT", "NVDA"],
)

print(r2["event_overlay"])
