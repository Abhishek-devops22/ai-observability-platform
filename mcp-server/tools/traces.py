"""get_traces — search Tempo for traces by service, with optional
minimum-duration filtering (useful for "why was this slow" queries)."""

from __future__ import annotations

import time

from config import settings
from tools._clients import http_client


def get_traces(
    service_name: str,
    min_duration_ms: int | None = None,
    since_minutes: int = 15,
    limit: int = 20,
) -> dict:
    """Search Tempo for traces belonging to `service_name`, newest first.

    Set `min_duration_ms` to only return slow traces (e.g. 3000 to find
    traces slower than 3s) — useful when correlating a latency alert
    against the trace that caused it.
    """
    now = int(time.time())
    start = now - since_minutes * 60

    params = {
        "tags": f"service.name={service_name}",
        "start": start,
        "end": now,
        "limit": limit,
    }
    if min_duration_ms is not None:
        params["minDuration"] = f"{min_duration_ms}ms"

    resp = http_client().get(f"{settings.tempo_url}/api/search", params=params)
    resp.raise_for_status()
    data = resp.json()

    traces = [
        {
            "trace_id": t.get("traceID"),
            "root_service": t.get("rootServiceName"),
            "root_span": t.get("rootTraceName"),
            "duration_ms": t.get("durationMs"),
            "start_time_unix_nano": t.get("startTimeUnixNano"),
        }
        for t in data.get("traces", [])
    ]

    return {"service": service_name, "count": len(traces), "traces": traces}
