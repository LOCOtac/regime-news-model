from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

from .events_model import CompanyEvent, EventOverlayDecision, MacroEvent, RegimeState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OverlayConfig:
    macro_window_days: int = 3
    company_window_days: int = 7

    # Baseline multiplier by regime policy label
    base_risk_multiplier: dict = None

    # Macro classification keywords (simple + robust)
    high_severity_keywords: Tuple[str, ...] = (
        "FOMC", "FED", "RATE", "INTEREST",
        "CPI", "INFLATION",
        "NFP", "NONFARM", "JOBS", "UNEMPLOYMENT",
        "GDP",
    )
    tighten_stop_keywords: Tuple[str, ...] = (
        "FOMC", "FED", "RATE", "CPI", "INFLATION", "NFP", "NONFARM"
    )

    def __post_init__(self):
        if self.base_risk_multiplier is None:
            self.base_risk_multiplier = {
                "risk_on": 1.00,
                "late_cycle": 0.85,
                "transition": 0.70,
                "risk_off": 0.50,
            }


class EventOverlayEngine:
    """
    Portfolio-level risk governor.

    Inputs:
      - RegimeState (policy regime + confidence)
      - Macro calendar events (TradingEconomics)
      - Company calendar events (FMP stable)

    Output:
      - allow_new_positions
      - risk_multiplier
      - tighten_stops
      - notes
    """

    def __init__(self, cfg: Optional[OverlayConfig] = None):
        self.cfg = cfg or OverlayConfig()

    def _within_window(self, events: Iterable, days: int) -> List:
        now = _utc_now()
        end = now + timedelta(days=days)
        out = []
        for e in events:
            dt = getattr(e, "datetime_utc", None)
            if dt and now <= dt <= end:
                out.append(e)
        return sorted(out, key=lambda x: x.datetime_utc)

    def _macro_severity(self, e: MacroEvent) -> float:
        """
        Severity score 0..1:
          - base from importance 1..3
          - bump if event name matches key macro catalysts
        """
        imp = int(e.importance or 1)
        base = {1: 0.25, 2: 0.55, 3: 0.85}.get(imp, 0.35)

        name = (e.event or "").upper()
        if any(k in name for k in self.cfg.high_severity_keywords):
            base = min(1.0, base + 0.15)

        return float(base)

    def _tighten_stops(self, macro_events: Sequence[MacroEvent]) -> bool:
        for e in macro_events:
            if int(e.importance or 1) < 2:
                continue
            name = (e.event or "").upper()
            if any(k in name for k in self.cfg.tighten_stop_keywords):
                return True
        return False

    def decide(
        self,
        regime: RegimeState,
        macro_events: Sequence[MacroEvent],
        company_events: Sequence[CompanyEvent],
        portfolio_symbols: Optional[Sequence[str]] = None,
    ) -> EventOverlayDecision:
        cfg = self.cfg
        notes: List[str] = []

        base_mult = float(cfg.base_risk_multiplier.get(regime.regime_name, 0.75))
        allow_new = True
        tighten_stops = False

        notes.append(f"Regime={regime.regime_name} conf={regime.confidence:.2f} base_mult={base_mult:.2f}")

        upcoming_macro = self._within_window(macro_events, cfg.macro_window_days)
        upcoming_company = self._within_window(company_events, cfg.company_window_days)

        # ---- Macro overlay ----
        if upcoming_macro:
            worst = max(upcoming_macro, key=self._macro_severity)
            worst_sev = self._macro_severity(worst)

            notes.append(
                f"Macro({cfg.macro_window_days}d) n={len(upcoming_macro)} worst='{worst.event}' "
                f"imp={worst.importance} sev={worst_sev:.2f}"
            )

            tighten_stops = self._tighten_stops(upcoming_macro)
            if tighten_stops:
                notes.append("Tighten stops: major macro catalyst in window.")

            # Institutional-style gating rules
            if regime.regime_name == "risk_off" and worst_sev >= 0.70:
                allow_new = False
                base_mult *= 0.70
                notes.append("Risk-off + high-severity macro -> block new positions; reduce risk.")
            elif regime.regime_name == "transition" and worst_sev >= 0.70:
                allow_new = False
                base_mult *= 0.80
                notes.append("Transition + high-severity macro -> block new positions; defensive posture.")
            elif worst_sev >= 0.85:
                base_mult *= 0.85
                notes.append("Very high macro severity -> reduce risk multiplier.")
        else:
            notes.append(f"No macro events in {cfg.macro_window_days}d window.")

        # ---- Company overlay (earnings-centric) ----
        symset = None
        if portfolio_symbols:
            symset = {s.upper().strip() for s in portfolio_symbols if s and s.strip()}

        if upcoming_company:
            relevant = [e for e in upcoming_company if symset is None or e.symbol in symset]
            earnings = [e for e in relevant if e.event_type == "earnings"]

            if earnings:
                impacted = sorted({e.symbol for e in earnings})
                notes.append(
                    f"Earnings({cfg.company_window_days}d) n={len(earnings)} "
                    f"impacted={impacted[:12]}{'...' if len(impacted) > 12 else ''}"
                )

                # Portfolio-level haircut (symbol-level sizing can be added later)
                if regime.regime_name in ("late_cycle", "transition"):
                    base_mult *= 0.90
                    notes.append("Late-cycle/Transition + earnings -> reduce portfolio risk modestly.")
                elif regime.regime_name == "risk_off":
                    base_mult *= 0.85
                    notes.append("Risk-off + earnings -> reduce portfolio risk.")
            else:
                notes.append(f"Company events({cfg.company_window_days}d) n={len(relevant)} (no earnings).")
        else:
            notes.append(f"No company events in {cfg.company_window_days}d window.")

        # ---- Confidence adjustment ----
        if regime.confidence < 0.55:
            base_mult *= 0.92
            notes.append("Low regime confidence -> reduce risk modestly.")

        # Clamp
        risk_mult = float(max(0.10, min(base_mult, 1.25)))

        return EventOverlayDecision(
            allow_new_positions=bool(allow_new),
            risk_multiplier=risk_mult,
            tighten_stops=bool(tighten_stops),
            notes=" | ".join(notes),
        )
