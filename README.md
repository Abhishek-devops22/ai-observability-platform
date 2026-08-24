# AI-Native Kubernetes Observability Platform

> Production-grade observability, AI-powered root cause analysis, predictive
> failure detection, and automated remediation — built on Kubernetes,
> OpenTelemetry, MCP Server, Grafana, Prometheus, Loki, Tempo, and Machine
> Learning.

This platform helps DevOps and SRE teams move from **reactive monitoring**
to **predictive operations**: it collects logs, metrics, traces, and
Kubernetes events, feeds them to an AI layer that explains *why* something
broke and predicts what's *about to* break, and can propose (or, with
approval, execute) a fix.

**Core capabilities**

- OpenTelemetry collection of logs, metrics, traces, and Kubernetes events
- Centralized storage with Prometheus, Loki, and Tempo
- MCP Server exposing observability tools to LLMs
- AI Root Cause Analysis (RCA) agent
- Semantic log search using embeddings + ChromaDB
- ML-based failure prediction
- Automated remediation recommendations, gated behind human approval
- Grafana dashboards and Alertmanager integration

---

## Table of contents

- [Quick start](#quick-start)
- [Environments — local vs. AWS](#environments--local-vs-aws)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Technology stack](#technology-stack)
- [How it works](#how-it-works)
- [REST API](#rest-api)
- [Grafana dashboards](#grafana-dashboards)
- [Security](#security)
- [CI/CD](#cicd)
- [Roadmap](#roadmap)
- [License](#license)

---

## Quick start

This section gets a novice engineer from a fresh clone to a running piece of
the platform. There are two paths:

- **[Path A — Local dev](#path-a--local-dev-no-cloud-account-needed)**: run
  the MCP server and AI engine on your laptop with mocked backends. No AWS
  account, no cost, no Kubernetes cluster. Best for exploring the code,
  running tests, or developing new tools/models. **Start here.**
- **[Path B — Full cluster deploy](#path-b--full-cluster-deploy)**:
  provision a real EKS cluster and the full observability stack with
  Terraform + Helm. Costs real AWS money.

### Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| [Python](https://www.python.org/downloads/) | 3.11+ | MCP server, AI engine, dataset scripts |
| [Git](https://git-scm.com/downloads) | any recent | cloning the repo |
| [Make](https://www.gnu.org/software/make/) | any | the shortcuts in `Makefile` (optional but recommended) |
| [Terraform](https://developer.hashicorp.com/terraform/install) | 1.6+ | Path B only — provisioning AWS infra |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) + an AWS account | v2 | Path B only |
| [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl) | 1.31+ | Path B only — talking to the cluster |
| [Helm](https://helm.sh/docs/intro/install/) | 3.x | Path B only — installing the observability stack |
| [Docker](https://docs.docker.com/get-docker/) | any recent | optional — building the MCP server image |

macOS users on Apple Silicon/Intel will also need `brew install libomp` for
the AI engine's `xgboost` dependency (see below).

### Path A — Local dev (no cloud account needed)

1. **Clone the repo**

   ```bash
   git clone https://github.com/Abhishek-devops22/ai-observability-platform.git
   cd ai-observability-platform
   ```

2. **Set up and run the MCP server** (exposes observability data as tools
   an LLM can call — see [Phase 4](#phase-4--mcp-server))

   ```bash
   make mcp-install   # creates mcp-server/.venv and installs dependencies
   make mcp-test       # runs the test suite against mocked Loki/Prometheus/Tempo/K8s — no live cluster needed
   ```

   To actually run the server, point it at real backends first:

   ```bash
   cd mcp-server
   cp .env.example .env   # edit .env: Prometheus/Loki/Tempo URLs + KUBECONFIG_PATH
   cd ..
   make mcp-run            # starts the server on stdio, for use with an MCP client / Claude Desktop
   ```

3. **Set up and run the AI engine** (RCA agent, anomaly detection, failure
   prediction, remediation — see [Phase 5](#phase-5--ai-intelligence-engine)
   and [Phase 6](#phase-6--remediation-engine))

   ```bash
   make ai-install   # creates ai-engine/.venv and installs dependencies
   make ai-test        # runs the test suite against synthetic data — no cluster, no Prometheus/Loki/Tempo/ChromaDB needed
   ```

   > macOS + xgboost needs the OpenMP runtime: `brew install libomp`.
   >
   > The LSTM forecaster in `ai-engine/prediction/` needs PyTorch, which is
   > kept out of the default install because the wheel is large:
   > `cd ai-engine && .venv/bin/pip install -r requirements-torch.txt`.

4. **(Optional) Generate a sample telemetry dataset** to feed the anomaly
   detection and prediction models:

   ```bash
   make dataset   # writes datasets/generated/telemetry.csv (5000 rows)
   ```

5. **(Optional) Explore the data** in `notebooks/01_exploratory_analysis.ipynb`
   with Jupyter (`pip install jupyterlab && jupyter lab`).

6. **(Optional) Run Prometheus + Grafana locally** with Docker Compose —
   no Kubernetes cluster needed:

   ```bash
   cd local-dev
   docker compose up -d
   ```

   - Prometheus: http://localhost:9090 (scrapes itself + a local
     `node-exporter`, so `up` and host metrics are real, queryable data)
   - Grafana: http://localhost:3000 (login `admin` / `admin`) — the three
     dashboards from `dashboards/` are auto-provisioned under the
     "AI Observability Platform" folder
   - Point `mcp-server/.env`'s `PROMETHEUS_URL` at `http://localhost:9090`
     (already the default) and the MCP server's `get_metrics` tool can
     query it

   These dashboards were designed for the full cluster deploy (Path B) —
   most panels expect `kube-state-metrics`, cAdvisor, OTel, and the AI
   engine's own metrics, so they'll show "No data" here. This stack is
   for exploring the Grafana/Prometheus setup and wiring the MCP server
   to a real metrics backend, not for a fully populated dashboard.
   Stop it with `docker compose down` (from `local-dev/`).

At this point you have a working MCP server, AI engine, and local
Prometheus/Grafana you can read, test, and extend — without touching AWS
or Kubernetes.

Run everything at once with `make test` (equivalent to `make mcp-test ai-test`).

### Path B — Full cluster deploy

This provisions a real EKS cluster on AWS and installs the full
observability stack. **This costs real AWS money** — tear it down with
`terraform destroy` when you're done.

1. **Configure AWS credentials** (`aws configure`, or environment
   variables/SSO — anything the AWS provider for Terraform accepts).

2. **Provision the infrastructure** (VPC, subnets, NAT gateway, EKS
   cluster, node group, IAM roles — see [Phase 1](#phase-1--infrastructure)):

   ```bash
   cd infrastructure/terraform
   cp terraform.tfvars.example terraform.tfvars   # adjust region/sizing as needed
   terraform init
   terraform plan     # or: make tf-plan
   terraform apply    # or: make tf-apply
   ```

3. **Point kubectl at the new cluster**:

   ```bash
   terraform output configure_kubectl   # prints the aws eks update-kubeconfig command — run it
   ```

4. **Install the observability stack** (namespaces, Prometheus, Loki,
   Tempo, the OpenTelemetry Collector, Grafana — see
   [Phase 2](#phase-2--kubernetes-observability) and
   [Phase 3](#phase-3--opentelemetry-collector)). Full command sequence,
   including Helm repo setup and dashboard imports, is in
   [`kubernetes/README.md`](kubernetes/README.md); the short version:

   ```bash
   make k8s-namespaces   # kubectl apply -f kubernetes/namespaces/namespaces.yaml
   # then follow kubernetes/README.md for the Helm installs (Prometheus, Loki,
   # Tempo, otel-collector, Grafana, in that order)
   ```

5. **Get the Grafana admin password, and a URL to reach it**:

   ```bash
   kubectl get secret grafana -n observability -o jsonpath="{.data.admin-password}" | base64 -d

   # kubernetes/README.md's install steps include an internal-facing ALB
   # Ingress for Grafana (kubernetes/grafana/ingress.yaml — VPC-only, not
   # public internet). Once it's provisioned (a minute or two):
   kubectl get ingress grafana -n observability -o jsonpath="{.status.loadBalancer.ingress[0].hostname}"

   # Or skip the ALB entirely:
   kubectl port-forward -n observability svc/grafana 3000:80
   ```

6. **Deploy the MCP server in-cluster** (optional — it can also run
   locally against the cluster via `kubectl port-forward`):

   ```bash
   docker build -t <registry>/ai-observability-mcp-server:latest mcp-server/
   docker push <registry>/ai-observability-mcp-server:latest
   make mcp-deploy-aws   # kubectl apply: namespace, ServiceAccount, RBAC, ConfigMap, Deployment, Service
   kubectl set image deployment/mcp-server -n mcp-server mcp-server=<registry>/ai-observability-mcp-server:latest
   ```

   See [`mcp-server/README.md`](mcp-server/README.md) "Running in-cluster"
   for what each manifest in `kubernetes/mcp-server/` does, and the
   [Environments](#environments--local-vs-aws) section below for how its
   config differs from local. Tear it down with `make mcp-undeploy-aws`.

   A real URL for it (vs. `kubectl port-forward`) is an explicit opt-in —
   `make mcp-ingress-aws` — **not** part of the steps above, because this
   server has no authentication of its own; read
   `kubernetes/mcp-server/ingress.yaml`'s header comment before deciding
   whether you want that.

7. **Tear down** when finished, to avoid ongoing AWS charges:

   ```bash
   cd infrastructure/terraform && terraform destroy
   ```

### Everyday commands

Once set up, the `Makefile` at the repo root is the fastest way in and out:

```bash
make help          # list every target with a one-line description
make test           # mcp-test + ai-test
make lint            # terraform fmt/validate + kubernetes YAML syntax check
make dataset         # regenerate the sample telemetry dataset
```

---

## Environments — local vs. AWS

Nothing in the application code branches on "which environment am I in" —
the MCP server (the one component that's an actual deployable service
today) reads plain environment variables via `pydantic-settings`
(`mcp-server/config.py`), and its Kubernetes client already
auto-detects whether it's running standalone or inside a pod
(`tools/_clients.py`: uses `KUBECONFIG_PATH` if set, otherwise falls back
to in-cluster auth via the pod's ServiceAccount token). So going from
local to AWS is entirely a matter of *what supplies those env vars*, not
a code change:

| | Local (Path A) | AWS (Path B) |
| --- | --- | --- |
| Backend URLs | `local-dev/` Compose stack, `localhost:9090/3100/3200` | in-cluster Service DNS (e.g. `prometheus-kube-prometheus-prometheus.observability.svc.cluster.local`) |
| Config source | `mcp-server/.env` (gitignored, from `.env.example`) | `kubernetes/mcp-server/configmap.yaml`, injected via `envFrom` |
| K8s auth | your kubeconfig / `KUBECONFIG_PATH` | pod ServiceAccount + RBAC (`kubernetes/mcp-server/rbac-*.yaml`) — no kubeconfig needed |
| Prometheus/Grafana | `local-dev/docker-compose.yml` (+ a synthetic-metrics `mock-exporter` — see `local-dev/mock-exporter/`) | Helm releases from `kubernetes/README.md`, backed by real cluster/app telemetry |
| Run it | `make local-up` | `make mcp-deploy-aws` (after `make tf-apply` + the Helm installs) |
| Tear down | `make local-down` | `make mcp-undeploy-aws` + `terraform destroy` |

To point the *local* MCP server at a *real* AWS cluster instead (e.g. to
poke at real data without deploying the server itself in-cluster), use
`mcp-server/.env.aws.example` — it's the same variables, just with
`kubectl port-forward` in front of them. Full detail:
[`mcp-server/README.md`](mcp-server/README.md) "Configuration — local vs.
AWS".

---

## Architecture

```text
                    Grafana Dashboards
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
     Prometheus          Loki             Tempo
    (Metrics)          (Logs)          (Traces)
        │                  │                  │
        └────────── OpenTelemetry Collector ──┘
                           │
        Kubernetes Cluster (Pods, Nodes, Events)
                           │
                    MCP Server (Tools)
                           │
         AI Intelligence Layer (LLM + ML Models)
                           │
       RCA • Prediction • Anomaly • Remediation
                           │
              Slack • Alertmanager • Argo
```

---

## Repository structure

```text
ai-observability-platform/
│
├── README.md
├── LICENSE
├── Makefile                 # make targets for every workflow below
│
├── infrastructure/          # Terraform: VPC, EKS, IAM (Phase 1)
│   ├── terraform/
│   ├── modules/
│   └── backend/
│
├── kubernetes/               # Helm values for the observability stack (Phase 2/3)
│   ├── namespaces/
│   ├── otel-collector/
│   ├── prometheus/
│   ├── loki/
│   ├── tempo/
│   ├── grafana/
│   ├── alertmanager/
│   └── mcp-server/             # Deployment/Service/RBAC/ConfigMap for the AWS environment
│
├── mcp-server/               # Exposes observability data as MCP tools (Phase 4)
│   ├── server.py
│   ├── config.py
│   ├── requirements.txt
│   └── tools/
│       ├── logs.py
│       ├── metrics.py
│       ├── traces.py
│       ├── events.py
│       ├── kubernetes.py
│       └── remediation.py
│
├── ai-engine/                 # RCA, embeddings, anomaly detection, prediction (Phase 5/6)
│   ├── ingestion/
│   ├── embeddings/
│   ├── vector_store/
│   ├── anomaly_detection/
│   ├── prediction/
│   ├── rca_agent/
│   └── remediation/
│
├── datasets/                  # Sample + synthetic telemetry data
│
├── dashboards/                 # Grafana dashboard JSON
│
├── local-dev/                    # docker-compose: Prometheus + Grafana for Path A
│
├── notebooks/                   # Exploratory analysis
│
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   └── RUNBOOKS.md
│
└── .github/
    └── workflows/                # CI/CD
```

Most subdirectories have their own README with setup detail specific to
that component: [`mcp-server/README.md`](mcp-server/README.md),
[`ai-engine/README.md`](ai-engine/README.md),
[`kubernetes/README.md`](kubernetes/README.md),
[`datasets/README.md`](datasets/README.md).

---

## Technology stack

| Layer | Technology |
| --- | --- |
| Platform | Kubernetes (EKS) |
| Infrastructure | Terraform |
| Telemetry | OpenTelemetry |
| Metrics | Prometheus |
| Logs | Loki |
| Traces | Tempo |
| Visualization | Grafana |
| Alerts | Alertmanager |
| AI Gateway | MCP Server |
| Vector Database | ChromaDB |
| Embeddings | Sentence Transformers |
| LLM | GPT / Claude / Llama |
| ML | PyTorch + Scikit-learn + XGBoost |
| Workflow | Argo Workflows |

---

## How it works

### Phase 1 — Infrastructure

Terraform provisions the AWS foundation: VPC with public/private subnets, a
NAT gateway, an EKS cluster with a managed node group, IAM roles, the EBS
CSI driver, and the Load Balancer Controller. See
[Path B, step 2](#path-b--full-cluster-deploy) above for the commands.

### Phase 2 — Kubernetes observability

Helm-installed components in the `observability` namespace:

- **Prometheus** — node metrics, pod metrics, kube-state-metrics, API
  server metrics
- **Loki** — application, system, and Kubernetes logs
- **Tempo** — distributed traces from OpenTelemetry
- **Grafana** — the Executive, SRE, and AI dashboards (see below)

Full install order and commands: [`kubernetes/README.md`](kubernetes/README.md).

### Phase 3 — OpenTelemetry Collector

- **Receivers**: OTLP, Filelog, Prometheus, Kubernetes Events, Jaeger
- **Processors**: Batch, Memory Limiter, Resource Detection, Attributes
  Enrichment
- **Exporters**: Loki (logs), Prometheus (metrics), Tempo (traces)

```text
Logs    → Receivers → Processors → Loki
Metrics → Receivers → Processors → Prometheus
Traces  → Receivers → Processors → Tempo
```

### Phase 4 — MCP Server

The MCP server exposes Kubernetes and observability data as tools an LLM
can call.

| Tool | Description | Mutates cluster state? |
| --- | --- | --- |
| `get_logs` | Query Loki (LogQL) | No |
| `get_metrics` | Query Prometheus (PromQL) | No |
| `get_traces` | Query Tempo | No |
| `get_events` | Kubernetes Events API | No |
| `describe_pod` | `kubectl describe` equivalent | No |
| `list_failed_pods` | Detect unhealthy pods | No |
| `restart_deployment` | Execute remediation | **Yes** — gated by `ALLOW_MUTATIONS` |
| `scale_deployment` | Horizontal scaling | **Yes** — gated by `ALLOW_MUTATIONS` |

The two mutating tools are disabled unless `ALLOW_MUTATIONS=true` is set
(see `mcp-server/.env.example`) — read-only by default, per the platform's
[security](#security) posture.

Example interaction:

```text
User: "Why is payment-service failing?"
  → LLM calls get_logs() → get_metrics() → get_traces() → Root Cause Analysis
```

Setup and deployment detail: [`mcp-server/README.md`](mcp-server/README.md).

### Phase 5 — AI Intelligence Engine

**1. Log ingestion → embeddings → vector store**

```text
Raw Logs → Cleaning → Chunking → Embeddings → Vector Database (ChromaDB)
```

Each chunk is stored with metadata like:

```json
{ "namespace": "prod", "pod": "payment-123", "severity": "ERROR", "service": "payment" }
```

**2. Semantic search** over that vector store, using BGE-small, MiniLM, or
E5-large embeddings, supports queries like:

- "Show database timeout errors"
- "Find all OOMKilled incidents"
- "Similar incidents from last month"

**3. Root Cause Analysis agent** correlates alerts, metrics, traces, logs,
and events into a ranked explanation:

```text
Alert → Metrics → Trace → Logs → Events → Root Cause → Confidence Score
```

```text
Issue: Database connection pool exhausted
Confidence: 94%
Evidence: CPU 97% · DB timeout spikes · Trace latency 3.8s
```

**4. Anomaly detection & failure prediction** over CPU, memory, disk,
network, error rate, restart count, and request latency:

| Model | Purpose |
| --- | --- |
| Isolation Forest | Unknown/unlabeled anomalies |
| LSTM | Time-series forecasting |
| XGBoost | Failure classification |

```text
Checkout Service — Failure Probability: 87% — ETA: 18 minutes — Likely Cause: Memory Leak
```

Component detail and how they fit together:
[`ai-engine/README.md`](ai-engine/README.md).

### Phase 6 — Remediation Engine

Every incident maps to a runbook action:

| Incident | Recommended action |
| --- | --- |
| CrashLoopBackOff | Restart deployment |
| OOMKilled | Increase memory |
| High CPU | Scale replicas |
| High latency | Investigate DB |
| ImagePullBackOff | Validate registry secret |

Mutating actions always go through an approval gate, never straight from
the model:

```text
AI Recommendation → Slack Approval → Argo Workflow → kubectl apply
```

### Dataset schema

The canonical telemetry record shared by the anomaly detector, the failure
predictor, and the notebooks (`datasets/schema.py`):

| Field | Type |
| --- | --- |
| timestamp | datetime |
| namespace | string |
| pod | string |
| cpu | float |
| memory | float |
| latency | float |
| errors | integer |
| restarts | integer |
| failed | boolean (target label: 0 = healthy, 1 = failure) |

---

## REST API

| Endpoint | Purpose |
| --- | --- |
| `/logs` | Search logs |
| `/metrics` | Metrics query |
| `/traces` | Trace explorer |
| `/rca` | Root cause analysis |
| `/predict` | Failure prediction |
| `/anomaly` | Detect anomalies |
| `/remediation` | Suggested fix |

Full request/response detail: [`docs/API.md`](docs/API.md).

---

## Grafana dashboards

Imported automatically by the Helm install in
[`kubernetes/README.md`](kubernetes/README.md), and versioned as JSON in
[`dashboards/`](dashboards/):

- **Executive** — cluster health score, active alerts, error budget, SLO
  compliance, predicted failures
- **SRE** — CPU & memory, network, pod restarts, trace latency, top error
  logs
- **AI** — anomaly timeline, failure probability, RCA confidence, similar
  historical incidents

---

## Security

- RBAC and namespace isolation
- TLS encryption
- Audit logs
- External Secrets for credential management
- MCP server is **read-only by default** — mutating tools require
  `ALLOW_MUTATIONS=true` and sit behind a Slack-approval / Argo Workflow
  gate in production, never invoked directly by the model

---

## CI/CD

Defined in [`.github/workflows/`](.github/workflows) (`ci.yml`, `cd.yml`):

```text
Git Push → GitHub Actions → Unit Tests → Docker Build → Security Scan → Push Image → Helm Deploy → Kubernetes
```

---

## Roadmap

| Week | Deliverable |
| --- | --- |
| 1 | Infrastructure + EKS |
| 2 | OpenTelemetry + Prometheus |
| 3 | Loki + Tempo + Grafana |
| 4 | MCP Server |
| 5 | AI log embeddings |
| 6 | RCA agent |
| 7 | ML prediction |
| 8 | Auto remediation |

**Future enhancements**: multi-cluster federation, cost-optimization AI,
reinforcement learning for SLO tuning, GitOps integration with ArgoCD, an
incident knowledge graph, and a natural-language Kubernetes assistant.

---

## License

[MIT](LICENSE) — © 2026 Abhishek Bharadwaj

**Author**: Abhishek Bharadwaj, Senior DevOps / Platform Engineer. This
project is designed as an enterprise portfolio piece demonstrating
Kubernetes, OpenTelemetry, AI, MLOps, and Platform Engineering.
