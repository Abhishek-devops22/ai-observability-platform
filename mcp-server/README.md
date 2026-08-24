# MCP Server

Exposes Kubernetes + observability (Loki, Prometheus, Tempo, Kubernetes
Events/API) as MCP tools an LLM client can call. See the root README's
"Phase 4 — MCP Server" for the tool table and example RCA flow.

## Configuration — local vs. AWS

Runtime config (`config.py`) is `pydantic-settings`: it reads real
environment variables the same way it reads a `.env` file, so the app
code itself never branches on "am I local or in the cluster?" — only
*where these values point* changes:

| | Local (Path A) | AWS in-cluster (Path B) |
| --- | --- | --- |
| Backend URLs | `localhost:9090/3100/3200` (or the `local-dev/` Compose stack, or a `kubectl port-forward`) | in-cluster Service DNS, e.g. `prometheus-kube-prometheus-prometheus.observability.svc.cluster.local` |
| Kubeconfig | your default kubeconfig / `KUBECONFIG_PATH` | unset — `tools/_clients.py` auto-falls-back to `load_incluster_config()` using the pod's ServiceAccount token |
| How config is supplied | `.env` file, gitignored | `kubernetes/mcp-server/configmap.yaml`, injected as env vars via `envFrom` |
| Template | `.env.example` (or `.env.aws.example` for testing locally against a real cluster) | `kubernetes/mcp-server/configmap.yaml` |

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

Build and push the image, then apply the manifests in
`kubernetes/mcp-server/` — a `Deployment` + `Service` in the `mcp-server`
namespace (created by `kubernetes/namespaces/namespaces.yaml`), a
`ServiceAccount`, and RBAC scoped to only the verbs the tools actually
need:

```bash
docker build -t <registry>/ai-observability-mcp-server:latest .
docker push <registry>/ai-observability-mcp-server:latest
# then edit the image in kubernetes/mcp-server/deployment.yaml, or:
#   kubectl set image deployment/mcp-server -n mcp-server \
#     mcp-server=<registry>/ai-observability-mcp-server:latest

kubectl apply -f kubernetes/namespaces/namespaces.yaml
kubectl apply -f kubernetes/mcp-server/serviceaccount.yaml
kubectl apply -f kubernetes/mcp-server/rbac-readonly.yaml
kubectl apply -f kubernetes/mcp-server/configmap.yaml
kubectl apply -f kubernetes/mcp-server/deployment.yaml
kubectl apply -f kubernetes/mcp-server/service.yaml

# Only if you also want restart_deployment / scale_deployment enabled —
# see rbac-mutate.yaml's comments before applying:
# kubectl apply -f kubernetes/mcp-server/rbac-mutate.yaml
# kubectl set env deployment/mcp-server -n mcp-server ALLOW_MUTATIONS=true
```

Or via `make` from the repo root: `make mcp-deploy-aws` (build+push still
manual — it needs your registry). `configmap.yaml`'s Service names/ports
are verified against the exact charts + values files in
`kubernetes/README.md` via `helm template` (not guessed — see that
file's header comment for the command). Re-verify if you bump a chart
version, and sanity-check against the running cluster too:

```bash
kubectl get svc -n observability
kubectl logs -n mcp-server deploy/mcp-server
```

By default this is only reachable inside the cluster (`kubectl
port-forward -n mcp-server svc/mcp-server 8080:8080`, or from another
pod at `mcp-server.mcp-server.svc.cluster.local:8080`). For a real URL
via an ALB, `make mcp-ingress-aws` — but **read
`kubernetes/mcp-server/ingress.yaml`'s header comment first**: this
server has no authentication of its own, so putting a load balancer in
front of it is a real security decision, not just a convenience one.
