"""Root Cause Analysis agent — README.md "Phase 5 — 3. Root Cause
Analysis Agent". Implements the reasoning workflow:

    Alert -> Metrics -> Trace -> Logs -> Events -> Root Cause -> Confidence Score

The agent doesn't call Loki/Prometheus/Tempo/Kubernetes directly — it's
decoupled from the MCP server on purpose (they're separate deployables;
see kubernetes/namespaces/namespaces.yaml: `mcp-server` vs `ai-engine`).
Instead it takes an `ObservabilityClient` (typically an MCP client
pointed at mcp-server/server.py) implementing the Protocol below, which
keeps this module testable without a live cluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ObservabilityClient(Protocol):
    """Matches the MCP server's read-only tool signatures
    (mcp-server/tools/*.py) — an MCP client implements this by calling
    those tools remotely."""

    def get_metrics(self, promql: str, since_minutes: int | None = None) -> dict: ...
    def get_traces(self, service_name: str, min_duration_ms: int | None = None) -> dict: ...
    def get_logs(self, namespace: str, pod: str | None = None, contains: str | None = None) -> dict: ...
    def get_events(self, namespace: str, object_name: str | None = None) -> dict: ...


@dataclass
class RCAResult:
    issue: str
    confidence: float  # 0-1
    evidence: list[str] = field(default_factory=list)

    def as_report(self) -> str:
        pct = round(self.confidence * 100)
        lines = [f"Issue:\n{self.issue}", "", f"Confidence:\n{pct}%", "", "Evidence:"]
        lines += [f"• {e}" for e in self.evidence]
        return "\n".join(lines)


# Each hypothesis: (issue label, PromQL to test, threshold, evidence template)
_HYPOTHESES = [
    {
        "issue": "Database connection pool exhausted",
        "metric_query": 'sum(rate(db_pool_wait_seconds_total{{namespace="{namespace}",service="{service}"}}[5m]))',
        "threshold": 0.1,
        "evidence": "DB timeout spikes",
    },
    {
        "issue": "Memory leak / OOM risk",
        "metric_query": 'max(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{pod}.*"}}) / max(kube_pod_container_resource_limits{{namespace="{namespace}",pod=~"{pod}.*",resource="memory"}})',
        "threshold": 0.85,
        "evidence": "Memory usage above 85% of limit",
    },
    {
        "issue": "CPU saturation",
        "metric_query": 'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{pod}.*"}}[5m]))',
        "threshold": 0.9,
        "evidence": "CPU usage above 90%",
    },
]

_CPU_THRESHOLD_MS = 3000


class RCAAgent:
    def __init__(self, client: ObservabilityClient):
        self.client = client

    def investigate(self, namespace: str, pod: str, service: str) -> RCAResult:
        """Run the Alert -> Metrics -> Trace -> Logs -> Events pipeline
        and return the best-supported root-cause hypothesis."""
        evidence: list[str] = []
        matched_issue: str | None = None
        signal_count = 0

        # 1. Metrics — test each hypothesis's PromQL against its threshold.
        for hypothesis in _HYPOTHESES:
            query = hypothesis["metric_query"].format(namespace=namespace, pod=pod, service=service)
            result = self.client.get_metrics(query)
            value = _extract_instant_value(result)
            if value is not None and value >= hypothesis["threshold"]:
                matched_issue = hypothesis["issue"]
                evidence.append(f"{hypothesis['evidence']} ({value:.2f})")
                signal_count += 1
                break  # first matching hypothesis wins; refine with more signals below

        # 2. Traces — slow traces corroborate a latency-flavored root cause.
        trace_result = self.client.get_traces(service, min_duration_ms=_CPU_THRESHOLD_MS)
        slow_traces = trace_result.get("traces", [])
        if slow_traces:
            slowest = max(t.get("duration_ms", 0) for t in slow_traces)
            evidence.append(f"Trace latency {slowest / 1000:.1f}s")
            signal_count += 1
            matched_issue = matched_issue or "Latency degradation"

        # 3. Logs — an error-severity hit corroborates whatever we've found.
        log_result = self.client.get_logs(namespace, pod=pod, contains="ERROR")
        error_logs = log_result.get("logs", [])
        if error_logs:
            evidence.append(f"{len(error_logs)} ERROR log lines in the last window")
            signal_count += 1
            matched_issue = matched_issue or "Application error"

        # 4. Events — CrashLoopBackOff/OOMKilled etc. are strong direct evidence.
        event_result = self.client.get_events(namespace, object_name=pod)
        warning_events = [e for e in event_result.get("events", []) if e.get("type") == "Warning"]
        if warning_events:
            reasons = sorted({e["reason"] for e in warning_events})
            evidence.append(f"Kubernetes events: {', '.join(reasons)}")
            signal_count += 1
            matched_issue = matched_issue or reasons[0]

        if matched_issue is None:
            return RCAResult(issue="No clear root cause identified", confidence=0.0, evidence=evidence)

        confidence = min(0.99, 0.5 + 0.12 * signal_count)  # more corroborating signals -> higher confidence
        return RCAResult(issue=matched_issue, confidence=confidence, evidence=evidence)


def _extract_instant_value(metrics_result: dict) -> float | None:
    """Pull the scalar value out of a Prometheus instant-query result
    shaped like tools/metrics.get_metrics()'s return value."""
    result = metrics_result.get("result", {}).get("result", [])
    if not result:
        return None
    try:
        return float(result[0]["value"][1])
    except (KeyError, IndexError, ValueError, TypeError):
        return None
