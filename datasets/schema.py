"""Canonical telemetry record schema, shared by the synthetic data
generator, ai-engine's anomaly_detection/prediction modules, and the
notebooks. Matches README.md "Dataset Schema".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

COLUMNS = ["timestamp", "namespace", "pod", "cpu", "memory", "latency", "errors", "restarts", "failed"]

DTYPES = {
    "timestamp": "datetime64[ns]",
    "namespace": "string",
    "pod": "string",
    "cpu": "float64",  # fraction of requested CPU, 0-1+
    "memory": "float64",  # fraction of requested memory, 0-1+
    "latency": "float64",  # ms, p99 request latency
    "errors": "int64",  # error count in the sampling window
    "restarts": "int64",  # cumulative container restart count
    "failed": "bool",  # target label: True = this sample precedes a failure
}


@dataclass
class TelemetryRecord:
    timestamp: datetime
    namespace: str
    pod: str
    cpu: float
    memory: float
    latency: float
    errors: int
    restarts: int
    failed: bool

    def as_row(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "namespace": self.namespace,
            "pod": self.pod,
            "cpu": self.cpu,
            "memory": self.memory,
            "latency": self.latency,
            "errors": self.errors,
            "restarts": self.restarts,
            "failed": self.failed,
        }
