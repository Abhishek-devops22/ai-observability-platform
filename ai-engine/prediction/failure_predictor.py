"""XGBoost failure classifier — README.md "Phase 5 — 4. Anomaly
Detection" table: "XGBoost | Failure classification". Trains on the
dataset schema in datasets/ (cpu, memory, latency, errors, restarts ->
failed 0/1) and produces a probability plus a rule-based "likely cause"
(the feature most out of line with its training-set norm), matching the
README's example output shape:

    Failure Probability: 87%
    Likely Cause: Memory Leak
"""

from __future__ import annotations

import pandas as pd
import xgboost as xgb

FEATURE_COLUMNS = ["cpu", "memory", "latency", "errors", "restarts"]
LABEL_COLUMN = "failed"

_CAUSE_LABELS = {
    "cpu": "High CPU",
    "memory": "Memory Leak",
    "latency": "Latency Degradation",
    "errors": "Elevated Error Rate",
    "restarts": "Crash Looping",
}


class FailurePredictor:
    def __init__(self, **xgb_params):
        params = {"n_estimators": 200, "max_depth": 4, "eval_metric": "logloss", **xgb_params}
        self.model = xgb.XGBClassifier(**params)
        self._train_mean = None
        self._train_std = None
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> "FailurePredictor":
        _validate_columns(df)
        X, y = df[FEATURE_COLUMNS], df[LABEL_COLUMN]
        self.model.fit(X, y)

        # Keep training-set stats so predict() can explain *why* — the
        # feature furthest (in std-devs) from its healthy-population mean.
        healthy = df[df[LABEL_COLUMN] == 0][FEATURE_COLUMNS]
        self._train_mean = healthy.mean()
        self._train_std = healthy.std().replace(0, 1e-9)
        self._fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> list[dict]:
        """Return one result per row: failure probability (0-1) and the
        likely-cause feature, ranked by how many standard deviations it
        sits from the healthy-population mean."""
        if not self._fitted:
            raise RuntimeError("Call fit() before predict()")
        _validate_columns(df, require_label=False)

        X = df[FEATURE_COLUMNS]
        probabilities = self.model.predict_proba(X)[:, 1]

        z_scores = (X - self._train_mean) / self._train_std

        results = []
        for i in range(len(df)):
            top_feature = z_scores.iloc[i].abs().idxmax()
            results.append(
                {
                    "failure_probability": float(probabilities[i]),
                    "likely_cause": _CAUSE_LABELS[top_feature],
                    "contributing_feature": top_feature,
                    "z_score": float(z_scores.iloc[i][top_feature]),
                }
            )
        return results


def _validate_columns(df: pd.DataFrame, require_label: bool = True) -> None:
    required = set(FEATURE_COLUMNS) | ({LABEL_COLUMN} if require_label else set())
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {sorted(missing)}")
