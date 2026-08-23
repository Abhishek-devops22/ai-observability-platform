# Architecture

## Deployment topology

Four Kubernetes namespaces (`kubernetes/namespaces/namespaces.yaml`):

| Namespace       | Contains |
| ---------------- | -------- |
| `observability`   | OTel Collector, Prometheus, Loki, Tempo, Grafana, Alertmanager |
| `mcp-server`       | The MCP server (`mcp-server/`) — read-only by default, exposes 8 tools |
| `ai-engine`        | RCA agent, anomaly detection, failure prediction, remediation engine |
| `argo`             | Argo Workflows — executes approved remediations |

## Data flow

```text
Kubernetes Pods/Nodes/Events
        │
        ▼
OpenTelemetry Collector (daemonset)
        │
   ┌────┼────┐
   ▼    ▼    ▼
 Loki Prometheus Tempo
   │    │    │
   └────┼────┘
        ▼
   Grafana (dashboards/*.json)
        │
        ▼
   MCP Server (mcp-server/) ──── exposes get_logs/get_metrics/get_traces/
        │                        get_events/describe_pod/list_failed_pods/
        │                        restart_deployment/scale_deployment
        ▼
   AI Engine (ai-engine/)
     rca_agent.RCAAgent.investigate()
        │  Alert -> Metrics -> Trace -> Logs -> Events -> Root Cause -> Confidence
        ▼
     remediation.engine.recommend()
        │  incident -> runbook action (docs/RUNBOOKS.md)
        ▼
   Slack Approval -> Argo Workflow -> mcp-server restart_deployment/scale_deployment
```

## Why the MCP server and AI engine are separate services

`ai-engine/rca_agent/agent.py` depends on an `ObservabilityClient`
Protocol, not on `mcp-server/tools/*.py` directly. In production, an MCP
client inside the AI engine calls the MCP server over the network
(stdio locally, `streamable-http` in-cluster — see
`mcp-server/config.py`'s `TRANSPORT` setting). This keeps:

- the MCP server's tool surface usable by *any* MCP client (Claude
  Desktop, other agents), not just this platform's RCA agent
- the read-only/mutating boundary enforced in one place
  (`mcp-server/tools/remediation.py`'s `ALLOW_MUTATIONS` gate)
- `ai-engine` unit-testable with a fake client (see
  `ai-engine/tests/test_rca_agent.py`) instead of requiring a live
  cluster to run its test suite

## Infrastructure

`infrastructure/terraform/` composes three modules
(`infrastructure/modules/{vpc,iam,eks}/`) into one EKS cluster:

```text
vpc  ──creates VPC + public/private subnets + NAT──┐
                                                     ├─▶ eks (cluster, node group, OIDC provider,
iam  ──creates cluster-role + node-role────────────┘     EBS CSI + LB Controller IRSA roles, addons)
```

The IAM roles for IRSA (EBS CSI driver, AWS Load Balancer Controller)
live inside the `eks` module rather than `iam`, because they need the
cluster's OIDC provider ARN, which doesn't exist until the cluster does
— putting them in `iam` would create a circular module dependency.

State: `infrastructure/backend/` is a small bootstrap stack (S3 bucket +
DynamoDB lock table) applied once by hand, with local state. The main
`infrastructure/terraform/` stack then migrates to that S3 backend — see
`infrastructure/terraform/providers.tf`.

## Security posture

See root README "Security". Concretely:

- `mcp-server`'s two mutating tools (`restart_deployment`,
  `scale_deployment`) raise `MutationsDisabledError` unless
  `ALLOW_MUTATIONS=true` — off by default.
- RBAC scoping for the MCP server's ServiceAccount is a tracked
  follow-up (see `mcp-server/README.md`).
- Alertmanager receiver secrets (Slack webhook, PagerDuty key) are
  file-mounted (`slack_api_url_file`, `service_key_file` in
  `kubernetes/alertmanager/alertmanager.yaml`), meant to be populated by
  External Secrets rather than committed.
