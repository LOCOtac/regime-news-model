from __future__ import annotations

from typing import Dict

from .events_model import RegimeState


def _max_prob(regime_probs: Dict[str, float]) -> float:
    if not regime_probs:
        return 0.0
    try:
        return float(max(regime_probs.values()))
    except Exception:
        return 0.0


def map_regime_to_policy(regime_id: int, regime_probs: Dict[str, float]) -> RegimeState:
    """
    v1 mapping:
      - If probabilities are mixed (low max prob), treat as 'transition'
      - Otherwise map numeric regimes to policy regimes

    NOTE:
    Your run_pipeline() currently restricts n_regimes to 2 or 3. :contentReference[oaicite:2]{index=2}
    For n_regimes=3, this default mapping is a reasonable starting point,
    but you SHOULD later re-map based on cluster stats (vol/drawdown/trend).
    """
    conf = _max_prob(regime_probs)

    # If regime is uncertain, it is safer to govern as "transition"
    if conf < 0.60:
        return RegimeState(regime_name="transition", confidence=conf, regime_id=int(regime_id))

    # Default heuristic mapping (v1)
    # You can later learn the mapping by computing cluster means.
    mapping_3 = {
        0: "risk_on",
        1: "late_cycle",
        2: "risk_off",
    }

    mapping_2 = {
        0: "risk_on",
        1: "risk_off",
    }

    if regime_id in mapping_3:
        name = mapping_3[regime_id]
    elif regime_id in mapping_2:
        name = mapping_2[regime_id]
    else:
        name = "transition"

    return RegimeState(regime_name=name, confidence=conf, regime_id=int(regime_id))
