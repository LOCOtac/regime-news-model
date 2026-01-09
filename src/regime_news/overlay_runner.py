from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional, Sequence

from .event_overlay import EventOverlayEngine, OverlayConfig
from .providers_fmp_events import FMPStableEventsClient
from .providers_fmp_macro import FMPMacroCalendarClient
from .regime_policy import map_regime_to_policy


def add_event_overlay_to_report(
    report: Dict[str, Any],
    *,
    portfolio_symbols: Optional[Sequence[str]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    macro_importance: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Non-invasive add-on:
      input:  report from run_pipeline()
      output: same report + report["event_overlay"] dict

    Your run_pipeline() report contains:
      - "regime" (int)
      - "regime_probs" (dict of p_regime_k)
    :contentReference[oaicite:4]{index=4}
    """
    start = start or date.today()
    end = end or (start + timedelta(days=7))

    regime_id = int(report.get("regime", -1))
    regime_probs = report.get("regime_probs", {}) or {}
    regime_state = map_regime_to_policy(regime_id, regime_probs)

    # Fetch event
   
    fmp = FMPStableEventsClient()

    macro = FMPMacroCalendarClient().get_calendar(start=start, end=end)

    earnings = fmp.earnings(start, end, symbols=portfolio_symbols)
    dividends = fmp.dividends(start, end, symbols=portfolio_symbols)
    splits = fmp.splits(start, end, symbols=portfolio_symbols)
    ipos = fmp.ipos(start, end)

    company = earnings + dividends + splits + ipos

    # Decision
    engine = EventOverlayEngine(OverlayConfig())
    decision = engine.decide(
        regime=regime_state,
        macro_events=macro,
        company_events=company,
        portfolio_symbols=portfolio_symbols,
    )

    out = dict(report)
    out["event_overlay"] = {
        "allow_new_positions": decision.allow_new_positions,
        "risk_multiplier": decision.risk_multiplier,
        "tighten_stops": decision.tighten_stops,
        "notes": decision.notes,
        "regime_policy": {
            "regime_name": regime_state.regime_name,
            "confidence": regime_state.confidence,
            "regime_id": regime_state.regime_id,
        },
        "windows": {"macro_window_days": 3, "company_window_days": 7},
        "asof_overlay_window_start": start.isoformat(),
        "asof_overlay_window_end": end.isoformat(),
    }
    return out
