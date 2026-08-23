import numpy as np
import pandas as pd
import pytest

from prediction.failure_predictor import FailurePredictor


def _synthetic_dataset(n=300, seed=1):
    rng = np.random.default_rng(seed)
    healthy_n = n // 2
    failing_n = n - healthy_n

    healthy = pd.DataFrame(
        {
            "cpu": rng.normal(0.3, 0.05, healthy_n),
            "memory": rng.normal(0.4, 0.05, healthy_n),
            "latency": rng.normal(120, 10, healthy_n),
            "errors": rng.poisson(1, healthy_n),
            "restarts": rng.integers(0, 2, healthy_n),
            "failed": 0,
        }
    )
    failing = pd.DataFrame(
        {
            "cpu": rng.normal(0.3, 0.05, failing_n),
            "memory": rng.normal(0.96, 0.02, failing_n),  # memory-leak flavored failures
            "latency": rng.normal(130, 10, failing_n),
            "errors": rng.poisson(2, failing_n),
            "restarts": rng.integers(0, 2, failing_n),
            "failed": 1,
        }
    )
    return pd.concat([healthy, failing], ignore_index=True)


def test_predict_requires_fit_first():
    predictor = FailurePredictor()
    df = _synthetic_dataset()
    with pytest.raises(RuntimeError):
        predictor.predict(df)


def test_predicts_higher_probability_for_memory_leak_pattern():
    df = _synthetic_dataset()
    predictor = FailurePredictor(n_estimators=50).fit(df)

    healthy_case = pd.DataFrame([{"cpu": 0.3, "memory": 0.4, "latency": 120, "errors": 1, "restarts": 0}])
    failing_case = pd.DataFrame([{"cpu": 0.3, "memory": 0.97, "latency": 130, "errors": 2, "restarts": 0}])

    healthy_result = predictor.predict(healthy_case)[0]
    failing_result = predictor.predict(failing_case)[0]

    assert failing_result["failure_probability"] > healthy_result["failure_probability"]
    assert failing_result["likely_cause"] == "Memory Leak"
