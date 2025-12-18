from __future__ import annotations
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture

def fit_gmm_regimes(feats: pd.DataFrame, n_regimes: int = 4, random_state: int = 7):
    scaler = StandardScaler()
    X = scaler.fit_transform(feats.values)

    gmm = GaussianMixture(
        n_components=n_regimes,
        covariance_type="full",
        n_init=10,
        random_state=random_state,
    )
    gmm.fit(X)

    probs = gmm.predict_proba(X)
    regime = probs.argmax(axis=1)

    out = feats.copy()
    out["regime"] = regime
    for k in range(n_regimes):
        out[f"p_regime_{k}"] = probs[:, k]
    return out, gmm, scaler
