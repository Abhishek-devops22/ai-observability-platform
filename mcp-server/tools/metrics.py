"""get_metrics — query Prometheus (PromQL), instant or range."""

from __future__ import annotations

import time

from config import settings
from tools._clients import http_client


def get_metrics(
    promql: str,
    since_minutes: int | None = None,
    step_seconds: int = 30,
) -> dict:
    """Run a PromQL query against Prometheus.

    If `since_minutes` is omitted, runs an instant query (current value).
    Otherwise runs a range query over the last `since_minutes` at
    `step_seconds` resolution.

    Common queries this platform's tools/agents use:
      - CPU:     sum(rate(container_cpu_usage_seconds_total{namespace="ns"}[5m])) by (pod)
      - Memory:  sum(container_memory_working_set_bytes{namespace="ns"}) by (pod)
      - Errors:  sum(rate(http_requests_total{status=~"5..",namespace="ns"}[5m])) by (service)
      - Restarts: kube_pod_container_status_restarts_total{namespace="ns"}
    """
    if since_minutes is None:
        resp = http_client().get(
            f"{settings.prometheus_url}/api/v1/query",
            params={"query": promql},
        )
        resp.raise_for_status()
        return {"query": promql, "type": "instant", "result": resp.json().get("data", {})}

    now = time.time()
    start = now - since_minutes * 60

    resp = http_client().get(
        f"{settings.prometheus_url}/api/v1/query_range",
        params={"query": promql, "start": start, "end": now, "step": step_seconds},
    )
    resp.raise_for_status()
    return {"query": promql, "type": "range", "result": resp.json().get("data", {})}
