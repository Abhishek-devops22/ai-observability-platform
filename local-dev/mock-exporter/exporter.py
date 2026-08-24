"""Synthetic metrics generator for the local-dev Prometheus/Grafana stack.

Emits fake-but-plausible series under the exact metric names + label sets
that dashboards/*.json query (container_*, kube_pod_info, http_requests_total,
traces_span_metrics_duration_milliseconds_bucket, ai_*) so the pre-built
Grafana dashboards have something to render locally, without a real
Kubernetes cluster, cAdvisor, kube-state-metrics, or the AI engine running.

This is local-dev-only scaffolding — it does not exist in the real
platform. It intentionally models one "unhealthy" service
(checkout-service in prod) so the dashboards tell a story similar to the
worked examples in the root README (elevated failure probability, high
trace latency, memory growth, restarts) rather than flat/empty panels.

Pure stdlib — no dependencies to install/build.
"""

from __future__ import annotations

import http.server
import random
import threading
import time

HOST = "0.0.0.0"
PORT = 9101
TICK_SECONDS = 5

# ---------------------------------------------------------------------------
# Synthetic topology
# ---------------------------------------------------------------------------

NAMESPACES = {
    "prod": ["payment-service", "checkout-service", "api-gateway"],
    "staging": ["payment-service", "checkout-service"],
}
REPLICAS_PER_SERVICE = 2
UNHEALTHY = ("prod", "checkout-service")  # the "incident" the dashboards should tell a story about

BUCKETS_MS = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

RCA_HISTORY = [
    ("prod", "database_connection_pool_exhausted", 0.94),
    ("prod", "checkout_service_memory_leak", 0.91),
    ("staging", "payment_service_high_latency", 0.78),
]


def _pods() -> list[tuple[str, str, str]]:
    """[(namespace, service, pod_name), ...]"""
    out = []
    for ns, services in NAMESPACES.items():
        for svc in services:
            for i in range(REPLICAS_PER_SERVICE):
                out.append((ns, svc, f"{svc}-7d9f6b7d9-{i:04x}"))
    return out


PODS = _pods()

# ---------------------------------------------------------------------------
# Mutable state, updated by the background ticker
# ---------------------------------------------------------------------------

_lock = threading.Lock()
state = {
    "cpu_seconds": {p: random.uniform(500, 2000) for p in PODS},
    "memory_bytes": {p: random.uniform(150e6, 400e6) for p in PODS},
    "net_rx_bytes": {p: random.uniform(1e6, 5e6) for p in PODS},
    "net_tx_bytes": {p: random.uniform(1e6, 5e6) for p in PODS},
    "restarts": {p: 0 for p in PODS},
    # namespace -> status -> count
    "http_requests": {ns: {"200": random.uniform(1000, 5000), "500": random.uniform(1, 20)} for ns in NAMESPACES},
    # (namespace, service) -> [cumulative bucket counts...]
    "trace_buckets": {(ns, svc): [0] * (len(BUCKETS_MS) + 1) for ns, services in NAMESPACES.items() for svc in services},
    "trace_count": {(ns, svc): 0 for ns, services in NAMESPACES.items() for svc in services},
}


def is_unhealthy(ns: str, svc: str) -> bool:
    return (ns, svc) == UNHEALTHY


def tick() -> None:
    with _lock:
        for ns, svc, pod in PODS:
            bad = is_unhealthy(ns, svc)

            state["cpu_seconds"][(ns, svc, pod)] += random.uniform(3.0, 6.0) if bad else random.uniform(0.3, 1.5)

            mem = state["memory_bytes"][(ns, svc, pod)]
            mem += random.uniform(8e6, 20e6) if bad else random.uniform(-5e6, 5e6)
            state["memory_bytes"][(ns, svc, pod)] = max(100e6, mem)

            state["net_rx_bytes"][(ns, svc, pod)] += random.uniform(0.5e6, 3e6)
            state["net_tx_bytes"][(ns, svc, pod)] += random.uniform(0.5e6, 3e6)

            if bad and random.random() < 0.15:
                state["restarts"][(ns, svc, pod)] += 1

        for ns in NAMESPACES:
            state["http_requests"][ns]["200"] += random.uniform(50, 200)
            bump = random.uniform(5, 25) if any(is_unhealthy(ns, s) for s in NAMESPACES[ns]) else random.uniform(0, 2)
            state["http_requests"][ns]["500"] += bump

        for ns, services in NAMESPACES.items():
            for svc in services:
                bad = is_unhealthy(ns, svc)
                n_samples = random.randint(5, 20)
                for _ in range(n_samples):
                    latency = random.lognormvariate(8.2, 0.5) if bad else random.lognormvariate(4.2, 0.6)
                    buckets = state["trace_buckets"][(ns, svc)]
                    for i, edge in enumerate(BUCKETS_MS):
                        if latency <= edge:
                            buckets[i] += 1
                    buckets[-1] += 1  # +Inf
                    state["trace_count"][(ns, svc)] += 1


def ticker_loop() -> None:
    while True:
        tick()
        time.sleep(TICK_SECONDS)


# ---------------------------------------------------------------------------
# Exposition format
# ---------------------------------------------------------------------------


def render() -> str:
    lines: list[str] = []

    lines.append("# HELP kube_pod_info Synthetic pod info (local-dev only)")
    lines.append("# TYPE kube_pod_info gauge")
    for ns, svc, pod in PODS:
        lines.append(f'kube_pod_info{{namespace="{ns}",pod="{pod}",service="{svc}"}} 1')

    with _lock:
        lines.append("# HELP container_cpu_usage_seconds_total Synthetic CPU seconds (local-dev only)")
        lines.append("# TYPE container_cpu_usage_seconds_total counter")
        for (ns, svc, pod), v in state["cpu_seconds"].items():
            lines.append(f'container_cpu_usage_seconds_total{{namespace="{ns}",pod="{pod}",service="{svc}"}} {v:.3f}')

        lines.append("# HELP container_memory_working_set_bytes Synthetic memory usage (local-dev only)")
        lines.append("# TYPE container_memory_working_set_bytes gauge")
        for (ns, svc, pod), v in state["memory_bytes"].items():
            lines.append(f'container_memory_working_set_bytes{{namespace="{ns}",pod="{pod}",service="{svc}"}} {v:.0f}')

        lines.append("# HELP container_network_receive_bytes_total Synthetic network rx (local-dev only)")
        lines.append("# TYPE container_network_receive_bytes_total counter")
        for (ns, svc, pod), v in state["net_rx_bytes"].items():
            lines.append(f'container_network_receive_bytes_total{{namespace="{ns}",pod="{pod}",service="{svc}"}} {v:.0f}')

        lines.append("# HELP container_network_transmit_bytes_total Synthetic network tx (local-dev only)")
        lines.append("# TYPE container_network_transmit_bytes_total counter")
        for (ns, svc, pod), v in state["net_tx_bytes"].items():
            lines.append(f'container_network_transmit_bytes_total{{namespace="{ns}",pod="{pod}",service="{svc}"}} {v:.0f}')

        lines.append("# HELP kube_pod_container_status_restarts_total Synthetic restart count (local-dev only)")
        lines.append("# TYPE kube_pod_container_status_restarts_total counter")
        for (ns, svc, pod), v in state["restarts"].items():
            lines.append(f'kube_pod_container_status_restarts_total{{namespace="{ns}",pod="{pod}",service="{svc}"}} {v}')

        lines.append("# HELP http_requests_total Synthetic HTTP request count (local-dev only)")
        lines.append("# TYPE http_requests_total counter")
        for ns, statuses in state["http_requests"].items():
            for status, v in statuses.items():
                lines.append(f'http_requests_total{{namespace="{ns}",status="{status}"}} {v:.0f}')

        lines.append("# HELP traces_span_metrics_duration_milliseconds Synthetic trace latency histogram (local-dev only)")
        lines.append("# TYPE traces_span_metrics_duration_milliseconds histogram")
        for (ns, svc), buckets in state["trace_buckets"].items():
            for edge, cum in zip(BUCKETS_MS, buckets[:-1]):
                lines.append(
                    f'traces_span_metrics_duration_milliseconds_bucket{{namespace="{ns}",service="{svc}",le="{edge}"}} {cum}'
                )
            lines.append(
                f'traces_span_metrics_duration_milliseconds_bucket{{namespace="{ns}",service="{svc}",le="+Inf"}} {buckets[-1]}'
            )
            count = state["trace_count"][(ns, svc)]
            lines.append(f'traces_span_metrics_duration_milliseconds_count{{namespace="{ns}",service="{svc}"}} {count}')
            lines.append(f'traces_span_metrics_duration_milliseconds_sum{{namespace="{ns}",service="{svc}"}} {count * 200}')

    lines.append("# HELP ai_predicted_failure_probability Synthetic AI failure prediction (local-dev only)")
    lines.append("# TYPE ai_predicted_failure_probability gauge")
    for ns, services in NAMESPACES.items():
        for svc in services:
            p = random.uniform(0.80, 0.93) if is_unhealthy(ns, svc) else random.uniform(0.01, 0.15)
            lines.append(f'ai_predicted_failure_probability{{namespace="{ns}",service="{svc}"}} {p:.3f}')

    lines.append("# HELP ai_anomaly_score Synthetic anomaly score (local-dev only)")
    lines.append("# TYPE ai_anomaly_score gauge")
    for ns, svc, pod in PODS:
        score = random.uniform(0.75, 0.97) if is_unhealthy(ns, svc) else random.uniform(0.02, 0.2)
        lines.append(f'ai_anomaly_score{{namespace="{ns}",pod="{pod}",service="{svc}"}} {score:.3f}')

    lines.append("# HELP ai_rca_confidence Synthetic RCA agent confidence for recent investigations (local-dev only)")
    lines.append("# TYPE ai_rca_confidence gauge")
    for ns, issue, confidence in RCA_HISTORY:
        lines.append(f'ai_rca_confidence{{namespace="{ns}",issue="{issue}"}} {confidence}')

    return "\n".join(lines) + "\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib API name)
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 (stdlib API name) - keep container logs quiet
        pass


def main() -> None:
    threading.Thread(target=ticker_loop, daemon=True).start()
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"mock-exporter serving synthetic metrics on {HOST}:{PORT}/metrics")
    server.serve_forever()


if __name__ == "__main__":
    main()
