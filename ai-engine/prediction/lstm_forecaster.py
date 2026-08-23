"""LSTM time-series forecaster — README.md "Phase 5 — 4. Anomaly
Detection" table: "LSTM | Time series prediction". Complements
failure_predictor.FailurePredictor (which classifies a single snapshot)
by forecasting where a metric is headed, which is what backs the
README's "ETA: 18 minutes" style output.

Requires `torch`, which is intentionally NOT in ai-engine/requirements.txt
(it's a large, platform-specific wheel) — install it separately:

    pip install -r requirements-torch.txt
"""

from __future__ import annotations

import numpy as np


class LSTMForecaster:
    """Thin wrapper around a small PyTorch LSTM that forecasts the next
    `horizon` steps of a single metric (e.g. memory usage) from a
    sliding window of history, so callers can estimate "time to
    threshold breach" (the README's ETA figure).
    """

    def __init__(self, window: int = 20, horizon: int = 5, hidden_size: int = 32):
        self.window = window
        self.horizon = horizon
        self.hidden_size = hidden_size
        self._model = None

    def _build(self):
        import torch.nn as nn

        window, horizon, hidden = self.window, self.horizon, self.hidden_size

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
                self.head = nn.Linear(hidden, horizon)

            def forward(self, x):
                _, (h_n, _) = self.lstm(x)
                return self.head(h_n[-1])

        return _Net()

    def fit(self, series: np.ndarray, epochs: int = 50, lr: float = 1e-3) -> "LSTMForecaster":
        """Fit on a single univariate series (e.g. one pod's memory usage
        over time), using a sliding window -> next-`horizon`-steps target."""
        import torch
        import torch.nn as nn

        X, y = _make_windows(series, self.window, self.horizon)
        if len(X) == 0:
            raise ValueError(f"series too short: need > window + horizon ({self.window + self.horizon}) points")

        self._model = self._build()
        optimizer = torch.optim.Adam(self._model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()

        X_t = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)  # (N, window, 1)
        y_t = torch.tensor(y, dtype=torch.float32)  # (N, horizon)

        self._model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            pred = self._model(X_t)
            loss = loss_fn(pred, y_t)
            loss.backward()
            optimizer.step()

        return self

    def forecast(self, recent_window: np.ndarray) -> np.ndarray:
        """Forecast the next `horizon` values given the most recent
        `window` observations."""
        import torch

        if self._model is None:
            raise RuntimeError("Call fit() before forecast()")
        if len(recent_window) != self.window:
            raise ValueError(f"recent_window must have exactly {self.window} points")

        self._model.eval()
        x = torch.tensor(recent_window, dtype=torch.float32).reshape(1, self.window, 1)
        with torch.no_grad():
            return self._model(x).squeeze(0).numpy()

    def eta_to_threshold(self, recent_window: np.ndarray, threshold: float, step_minutes: float) -> float | None:
        """Forecast forward and return minutes-until-`threshold` is
        crossed, or None if the forecast horizon never crosses it."""
        forecast = self.forecast(recent_window)
        crossings = np.where(forecast >= threshold)[0]
        if len(crossings) == 0:
            return None
        return float((crossings[0] + 1) * step_minutes)


def _make_windows(series: np.ndarray, window: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(series) - window - horizon + 1
    if n <= 0:
        return np.empty((0, window)), np.empty((0, horizon))
    X = np.stack([series[i : i + window] for i in range(n)])
    y = np.stack([series[i + window : i + window + horizon] for i in range(n)])
    return X, y
