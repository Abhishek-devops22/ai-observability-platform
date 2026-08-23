"""Unknown-anomaly detection via Isolation Forest, over the feature set
listed in README.md "Phase 5 — 4. Anomaly Detection": CPU, memory, disk,
network, error rate, restart count, request latency.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURE_COLUMNS = [
    "cpu",
    "memory",
    "latency",
    "errors",
    "restarts",
]


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.model = IsolationForest(contamination=contamination, random_state=random_state)
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> "AnomalyDetector":
        """Fit on historical "normal" telemetry. `df` must contain
        FEATURE_COLUMNS (see datasets/ for the shared schema)."""
        _validate_columns(df)
        self.model.fit(df[FEATURE_COLUMNS])
        self._fitted = True
        return self

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return `df` with two added columns:
          - anomaly_score: higher = more anomalous (inverted sklearn convention)
          - is_anomaly: bool
        """
        if not self._fitted:
            raise RuntimeError("Call fit() before score()")
        _validate_columns(df)

        raw_scores = self.model.decision_function(df[FEATURE_COLUMNS])  # higher = more normal
        predictions = self.model.predict(df[FEATURE_COLUMNS])  # -1 = anomaly, 1 = normal

        out = df.copy()
        out["anomaly_score"] = -raw_scores
        out["is_anomaly"] = predictions == -1
        return out


def _validate_columns(df: pd.DataFrame) -> None:
    missing = set(FEATURE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {sorted(missing)}")
