from rca_agent.agent import RCAAgent


class FakeClient:
    """Implements the ObservabilityClient protocol with canned responses
    shaped like the real MCP tools in mcp-server/tools/*.py."""

    def __init__(self, metric_values=None, traces=None, logs=None, events=None):
        self.metric_values = metric_values or {}
        self.traces = traces or []
        self.logs = logs or []
        self.events = events or []

    def get_metrics(self, promql, since_minutes=None):
        for substring, value in self.metric_values.items():
            if substring in promql:
                return {"result": {"result": [{"value": [0, str(value)]}]}}
        return {"result": {"result": []}}

    def get_traces(self, service_name, min_duration_ms=None):
        return {"traces": self.traces}

    def get_logs(self, namespace, pod=None, contains=None):
        return {"logs": self.logs}

    def get_events(self, namespace, object_name=None):
        return {"events": self.events}


def test_no_evidence_yields_no_root_cause():
    agent = RCAAgent(FakeClient())
    result = agent.investigate(namespace="prod", pod="payment-123", service="payment")
    assert result.confidence == 0.0
    assert "No clear root cause" in result.issue


def test_db_pool_and_slow_trace_corroborate_db_exhaustion():
    client = FakeClient(
        metric_values={"db_pool_wait_seconds_total": 0.5},
        traces=[{"duration_ms": 3800}],
        logs=[{"line": "ERROR db timeout"}],
        events=[{"type": "Warning", "reason": "Unhealthy"}],
    )
    agent = RCAAgent(client)

    result = agent.investigate(namespace="prod", pod="payment-123", service="payment")

    assert result.issue == "Database connection pool exhausted"
    assert result.confidence > 0.5
    assert any("Trace latency" in e for e in result.evidence)
    assert any("DB timeout spikes" in e for e in result.evidence)
    assert any("ERROR log lines" in e for e in result.evidence)


def test_more_corroborating_signals_increase_confidence():
    weak = FakeClient(metric_values={"db_pool_wait_seconds_total": 0.5})
    strong = FakeClient(
        metric_values={"db_pool_wait_seconds_total": 0.5},
        traces=[{"duration_ms": 4000}],
        logs=[{"line": "ERROR"}],
        events=[{"type": "Warning", "reason": "Unhealthy"}],
    )

    weak_result = RCAAgent(weak).investigate("prod", "pod", "svc")
    strong_result = RCAAgent(strong).investigate("prod", "pod", "svc")

    assert strong_result.confidence > weak_result.confidence
