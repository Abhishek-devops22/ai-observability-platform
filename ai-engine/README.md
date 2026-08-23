# AI Intelligence Engine

Implements README.md "Phase 5 — AI Intelligence Engine" and "Phase 6 —
Remediation Engine". Each subsystem is a standalone, unit-tested Python
package — none of them require a live cluster to test.

| Package               | Implements                                          |
| ---------------------- | ---------------------------------------------------- |
| `ingestion/`            | Raw logs -> cleaned, chunked `LogRecord`s            |
| `embeddings/`           | BGE-small / MiniLM / E5-large wrapper (lazy-loaded)  |
| `vector_store/`         | ChromaDB-backed semantic log search                  |
| `anomaly_detection/`    | Isolation Forest over CPU/memory/latency/errors/restarts |
| `prediction/`           | XGBoost failure classifier + optional LSTM forecaster (ETA-to-threshold) |
| `rca_agent/`            | Alert -> Metrics -> Trace -> Logs -> Events -> Root Cause -> Confidence |
| `remediation/`          | Incident -> recommended runbook action (README's incident table) |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional — only needed for prediction/lstm_forecaster.py:
pip install -r requirements-torch.txt
```

macOS + xgboost needs the OpenMP runtime: `brew install libomp`.

## Tests

```bash
pip install pytest
pytest -q
```

All tests run against synthetic data / fake clients — no Prometheus,
Loki, Tempo, ChromaDB, or Kubernetes cluster required. `rca_agent` is
decoupled from the MCP server on purpose: it depends on an
`ObservabilityClient` Protocol (see `rca_agent/agent.py`) that an MCP
client implements against the real `mcp-server/` at runtime.

## How the pieces fit together (Phase 5 → Phase 6 flow)

```text
Alert fires
   │
   ▼
RCAAgent.investigate()            (rca_agent/agent.py)
   │  queries metrics/traces/logs/events via an MCP client
   ▼
RCAResult(issue, confidence, evidence)
   │
   ▼
remediation.engine.recommend(issue)   (remediation/engine.py)
   │
   ▼
Recommendation(action, auto_approvable)
   │
   ▼
Slack approval -> Argo Workflow -> mcp-server restart_deployment / scale_deployment
```
