"""get_logs — query Loki (LogQL) for a namespace/pod/service."""

from __future__ import annotations

import time

from config import settings
from tools._clients import http_client


def get_logs(
    namespace: str,
    pod: str | None = None,
    contains: str | None = None,
    severity: str | None = None,
    since_minutes: int = 15,
    limit: int = 100,
) -> dict:
    """Search logs in Loki for a namespace, optionally scoped to a pod,
    a substring match, and/or a severity label (e.g. "ERROR").

    Returns a dict with the LogQL query used and the matching log lines
    (timestamp + line), newest first.
    """
    selector = f'namespace="{namespace}"'
    if pod:
        selector += f', pod=~"{pod}.*"'
    logql = "{" + selector + "}"
    if severity:
        logql += f' | json | severity=`{severity}`'
    if contains:
        logql += f' |= `{contains}`'

    now_ns = int(time.time() * 1e9)
    start_ns = now_ns - since_minutes * 60 * int(1e9)

    resp = http_client().get(
        f"{settings.loki_url}/loki/api/v1/query_range",
        params={
            "query": logql,
            "start": start_ns,
            "end": now_ns,
            "limit": limit,
            "direction": "backward",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    lines = []
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for ts, line in stream.get("values", []):
            lines.append({"timestamp_ns": ts, "labels": labels, "line": line})

    lines.sort(key=lambda x: x["timestamp_ns"], reverse=True)

    return {"query": logql, "count": len(lines), "logs": lines[:limit]}
