# MCP Server

Exposes Kubernetes + observability (Loki, Prometheus, Tempo, Kubernetes
Events/API) as MCP tools an LLM client can call. See the root README's
"Phase 4 — MCP Server" for the tool table and example RCA flow.

## Local dev

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point at your Prometheus/Loki/Tempo + kubeconfig
python server.py       # stdio transport, for use with an MCP client / Claude Desktop
```

Run the test suite (mocks all backends — no live cluster needed):

```bash
pip install pytest
pytest -q
```

## Tools

| Tool                 | Backend             | Mutates cluster state? |
| -------------------- | -------------------- | ----------------------- |
| `get_logs`            | Loki (LogQL)          | No |
| `get_metrics`          | Prometheus (PromQL)   | No |
| `get_traces`           | Tempo                 | No |
| `get_events`           | Kubernetes Events API | No |
| `describe_pod`         | Kubernetes API        | No |
| `list_failed_pods`     | Kubernetes API        | No |
| `restart_deployment`   | Kubernetes API        | **Yes** — gated by `ALLOW_MUTATIONS` |
| `scale_deployment`     | Kubernetes API        | **Yes** — gated by `ALLOW_MUTATIONS` |

The two mutating tools raise `MutationsDisabledError` unless
`ALLOW_MUTATIONS=true` is set — see `config.py`. This matches the
platform's "read-only MCP access by default" security posture; in
production these should sit behind the Slack-approval / Argo Workflow
gate described in the root README's remediation flow rather than being
invoked directly.

## Running in-cluster

Build and push the image, then deploy it into the `mcp-server` namespace
created by `kubernetes/namespaces/namespaces.yaml`, with a `ServiceAccount`
scoped (via RBAC) to only the namespaces/verbs it actually needs.

```bash
docker build -t <registry>/ai-observability-mcp-server:latest .
docker push <registry>/ai-observability-mcp-server:latest
```

A Kubernetes Deployment + RBAC manifest for this isn't included yet
(tracked as a follow-up) — for now, run it as a sidecar or via
`kubectl port-forward` during development.
