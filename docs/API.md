# REST API

Design spec for the REST API listed in the root README. **Not yet
implemented as a service** — today these capabilities exist as Python
functions (`mcp-server/tools/*.py`, `ai-engine/rca_agent/agent.py`,
`ai-engine/prediction/failure_predictor.py`, etc.) callable via MCP or
directly in-process. This doc is the contract a thin FastAPI wrapper
should implement when a REST surface (e.g. for a web dashboard) is
needed, so it's written before that wrapper to keep the two in sync.

All endpoints return JSON. Errors use `{"error": "<message>"}` with a
non-2xx status.

## `GET /logs`

Search logs. Wraps `mcp-server/tools/logs.get_logs`.

| Param | Type | Required | Notes |
|---|---|---|---|
| `namespace` | string | yes | |
| `pod` | string | no | prefix match |
| `contains` | string | no | substring filter |
| `severity` | string | no | e.g. `ERROR` |
| `since_minutes` | int | no | default 15 |
| `limit` | int | no | default 100 |

## `GET /metrics`

Run a PromQL query. Wraps `mcp-server/tools/metrics.get_metrics`.

| Param | Type | Required |
|---|---|---|
| `promql` | string | yes |
| `since_minutes` | int | no (omit for instant query) |
| `step_seconds` | int | no, default 30 |

## `GET /traces`

Search traces. Wraps `mcp-server/tools/traces.get_traces`.

| Param | Type | Required |
|---|---|---|
| `service_name` | string | yes |
| `min_duration_ms` | int | no |
| `since_minutes` | int | no, default 15 |

## `POST /rca`

Run root-cause analysis. Wraps `ai-engine/rca_agent/agent.py`'s
`RCAAgent.investigate`.

```json
// Request
{ "namespace": "prod", "pod": "payment-123", "service": "payment" }

// Response — RCAResult, see ai-engine/rca_agent/agent.py
{
  "issue": "Database connection pool exhausted",
  "confidence": 0.94,
  "evidence": ["DB timeout spikes (0.50)", "Trace latency 3.8s", "..."]
}
```

## `POST /predict`

Failure probability for a snapshot. Wraps
`ai-engine/prediction/failure_predictor.FailurePredictor.predict`.

```json
// Request
{ "cpu": 0.3, "memory": 0.97, "latency": 130, "errors": 2, "restarts": 0 }

// Response
{ "failure_probability": 0.87, "likely_cause": "Memory Leak", "contributing_feature": "memory" }
```

## `POST /anomaly`

Score telemetry rows for anomalies. Wraps
`ai-engine/anomaly_detection/isolation_forest.AnomalyDetector.score`.

```json
// Request: { "rows": [{ "cpu": ..., "memory": ..., "latency": ..., "errors": ..., "restarts": ... }, ...] }
// Response: { "results": [{ ...row, "anomaly_score": 0.71, "is_anomaly": true }, ...] }
```

## `POST /remediation`

Get the recommended action for an incident. Wraps
`ai-engine/remediation/engine.recommend`.

```json
// Request
{ "incident_reason": "CrashLoopBackOff" }

// Response
{ "incident": "CrashLoopBackOff", "action": "restart_deployment", "description": "Restart Deployment", "auto_approvable": true }
```
