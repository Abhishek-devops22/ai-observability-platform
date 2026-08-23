import numpy as np
import pandas as pd
import pytest

from anomaly_detection.isolation_forest import AnomalyDetector


def _synthetic_telemetry(n_normal=200, n_anomalous=10, seed=0):
    rng = np.random.default_rng(seed)
    normal = pd.DataFrame(
        {
            "cpu": rng.normal(0.3, 0.05, n_normal),
            "memory": rng.normal(0.4, 0.05, n_normal),
            "latency": rng.normal(120, 10, n_normal),
            "errors": rng.poisson(1, n_normal),
            "restarts": rng.integers(0, 2, n_normal),
        }
    )
    anomalous = pd.DataFrame(
        {
            "cpu": rng.normal(0.97, 0.02, n_anomalous),
            "memory": rng.normal(0.95, 0.02, n_anomalous),
            "latency": rng.normal(3800, 100, n_anomalous),
            "errors": rng.poisson(50, n_anomalous),
            "restarts": rng.integers(5, 10, n_anomalous),
        }
    )
    return normal, anomalous


def test_score_requires_fit_first():
    detector = AnomalyDetector()
    normal, _ = _synthetic_telemetry()
    with pytest.raises(RuntimeError):
        detector.score(normal)


def test_missing_columns_raise():
    detector = AnomalyDetector()
    with pytest.raises(ValueError):
        detector.fit(pd.DataFrame({"cpu": [0.1]}))


def test_flags_obviously_anomalous_rows():
    normal, anomalous = _synthetic_telemetry()
    detector = AnomalyDetector(contamination=0.05).fit(normal)

    scored = detector.score(pd.concat([normal, anomalous], ignore_index=True))

    # The synthetic "anomalous" rows should score as anomalies far more
    # often than the "normal" rows they're mixed in with.
    normal_flag_rate = scored.iloc[: len(normal)]["is_anomaly"].mean()
    anomalous_flag_rate = scored.iloc[len(normal):]["is_anomaly"].mean()
    assert anomalous_flag_rate > normal_flag_rate
