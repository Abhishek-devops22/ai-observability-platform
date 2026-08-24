#!/usr/bin/env bash
# AWS deploy for the AI Observability Platform (README.md "Quick start"
# Path B) — provisions a real EKS cluster and the full observability
# stack. THIS COSTS REAL AWS MONEY. Run `destroy` when you're done.
#
# This is a thin wrapper around the exact commands in README.md /
# kubernetes/README.md / mcp-server/README.md — read those if you want
# to understand or hand-run any individual step; this script just chains
# them with confirmation prompts before anything that costs money or
# creates a network-reachable endpoint.
#
# Usage:
#   scripts/run-aws.sh check            # verify aws/terraform/kubectl/helm/docker + AWS creds
#   scripts/run-aws.sh infra            # terraform apply — costs money — prompts to confirm
#   scripts/run-aws.sh kubeconfig       # point kubectl at the new cluster
#   scripts/run-aws.sh observability    # namespaces + ALB controller + Prometheus/Loki/Tempo/Grafana + Grafana Ingress
#   scripts/run-aws.sh mcp-server       # docker build+push (needs REGISTRY) + deploy into the cluster
#   scripts/run-aws.sh mcp-ingress      # OPT-IN: a real ALB for the MCP server — reads a security warning, asks to confirm
#   scripts/run-aws.sh urls             # print Grafana/MCP server URLs + Grafana password
#   scripts/run-aws.sh all              # infra + kubeconfig + observability + mcp-server, one confirmation upfront (NOT mcp-ingress)
#   scripts/run-aws.sh destroy          # tear down everything — prompts to confirm
#
# Flags:
#   -y, --yes     skip confirmation prompts (for CI; use deliberately)
#
# Env vars:
#   REGISTRY      required for `mcp-server` — e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-observability-mcp-server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TF_DIR="$REPO_ROOT/infrastructure/terraform"
K8S_DIR="$REPO_ROOT/kubernetes"

ASSUME_YES=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done
set -- "${ARGS[@]}"

log()  { printf '==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

confirm() {
  local prompt="$1"
  [[ "$ASSUME_YES" == "1" ]] && return 0
  read -r -p "$prompt Type 'yes' to continue: " reply
  [[ "$reply" == "yes" ]] || die "Aborted."
}

need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found on PATH."; }

# --- commands --------------------------------------------------------------

cmd_check() {
  need aws; need terraform; need kubectl; need helm; need docker
  log "AWS identity:"
  aws sts get-caller-identity || die "AWS credentials not configured/valid — run 'aws configure' or set up SSO first."
  log "All required tools present and AWS credentials valid."
}

cmd_infra() {
  need terraform
  [[ -f "$TF_DIR/terraform.tfvars" ]] || {
    log "No terraform.tfvars — copying from the example. Review it before continuing (region, sizing)."
    cp "$TF_DIR/terraform.tfvars.example" "$TF_DIR/terraform.tfvars"
  }
  confirm "This runs 'terraform apply' in $TF_DIR — provisions a real VPC + EKS cluster and WILL COST MONEY."
  (cd "$TF_DIR" && terraform init && terraform apply)
}

cmd_kubeconfig() {
  need terraform
  local cmd
  cmd="$(cd "$TF_DIR" && terraform output -raw configure_kubectl)"
  log "Running: $cmd"
  eval "$cmd"
}

cmd_observability() {
  need helm; need kubectl
  local cluster_name lb_role_arn

  kubectl apply -f "$K8S_DIR/namespaces/namespaces.yaml"

  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
  helm repo add grafana https://grafana.github.io/helm-charts >/dev/null
  helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null
  helm repo add eks https://aws.github.io/eks-charts >/dev/null
  helm repo update >/dev/null

  cluster_name="$(cd "$TF_DIR" && terraform output -raw cluster_name)"
  lb_role_arn="$(cd "$TF_DIR" && terraform output -raw lb_controller_role_arn)"
  log "AWS Load Balancer Controller (cluster: $cluster_name)..."
  helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
    -n kube-system \
    --set clusterName="$cluster_name" \
    --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="$lb_role_arn"

  log "Prometheus + Alertmanager..."
  helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    -n observability -f "$K8S_DIR/prometheus/values.yaml"
  kubectl create secret generic alertmanager-config -n observability \
    --from-file=alertmanager.yaml="$K8S_DIR/alertmanager/alertmanager.yaml" \
    --dry-run=client -o yaml | kubectl apply -f -

  log "Loki (MinIO-backed — generating fresh root credentials, not stored anywhere)..."
  helm upgrade --install loki grafana/loki -n observability -f "$K8S_DIR/loki/values.yaml" \
    --set minio.rootUser=loki-minio-admin \
    --set minio.rootPassword="$(openssl rand -base64 24)"

  log "Tempo..."
  helm upgrade --install tempo grafana/tempo -n observability -f "$K8S_DIR/tempo/values.yaml"

  log "OpenTelemetry Collector..."
  helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
    -n observability -f "$K8S_DIR/otel-collector/values.yaml"

  log "Grafana + dashboards..."
  helm upgrade --install grafana grafana/grafana -n observability -f "$K8S_DIR/grafana/values.yaml" \
    --set-file dashboards.default.executive.json="$REPO_ROOT/dashboards/executive-dashboard.json" \
    --set-file dashboards.default.sre.json="$REPO_ROOT/dashboards/sre-dashboard.json" \
    --set-file dashboards.default.ai.json="$REPO_ROOT/dashboards/ai-dashboard.json"

  log "Grafana Ingress (internal-facing ALB — see kubernetes/grafana/ingress.yaml)..."
  kubectl apply -f "$K8S_DIR/grafana/ingress.yaml"

  log "Observability stack installed. Run '$0 urls' in a minute or two once the ALB provisions."
}

cmd_mcp_server() {
  need docker; need kubectl
  [[ -n "${REGISTRY:-}" ]] || die "Set REGISTRY first, e.g. REGISTRY=123456789.dkr.ecr.us-east-1.amazonaws.com/ai-observability-mcp-server $0 mcp-server"

  log "Building and pushing $REGISTRY:latest ..."
  docker build -t "$REGISTRY:latest" "$REPO_ROOT/mcp-server"
  docker push "$REGISTRY:latest"

  log "Deploying (namespace, ServiceAccount, RBAC, ConfigMap, Deployment, Service)..."
  make -C "$REPO_ROOT" mcp-deploy-aws
  kubectl set image deployment/mcp-server -n mcp-server mcp-server="$REGISTRY:latest"
  kubectl rollout status deployment/mcp-server -n mcp-server --timeout=120s
}

cmd_mcp_ingress() {
  warn "The MCP server has NO authentication of its own. Read kubernetes/mcp-server/ingress.yaml's"
  warn "header comment before doing this — anything that can reach the resulting ALB can call its"
  warn "tools with zero credentials. scheme: internal (VPC-only) is the floor, not a fix."
  confirm "Provision a real ALB for the MCP server anyway?"
  make -C "$REPO_ROOT" mcp-ingress-aws
}

cmd_urls() {
  need kubectl
  echo
  echo "-- Grafana --"
  kubectl get ingress grafana -n observability -o jsonpath='http://{.status.loadBalancer.ingress[0].hostname}{"\n"}' 2>/dev/null \
    || echo "(Ingress not found/provisioned yet)"
  echo "admin password:"
  kubectl get secret grafana -n observability -o jsonpath="{.data.admin-password}" 2>/dev/null | base64 -d && echo || echo "(secret not found)"
  echo
  echo "-- MCP server --"
  kubectl get ingress mcp-server -n mcp-server -o jsonpath='http://{.status.loadBalancer.ingress[0].hostname}{"\n"}' 2>/dev/null \
    || echo "(no Ingress — run '$0 mcp-ingress' if you want one, or use: kubectl port-forward -n mcp-server svc/mcp-server 8080:8080)"
}

cmd_all() {
  confirm "This runs infra + kubeconfig + observability + mcp-server end to end. Provisions real, billed AWS resources (EKS, EBS volumes, an ALB)."
  ASSUME_YES=1
  cmd_infra
  cmd_kubeconfig
  cmd_observability
  cmd_mcp_server
  cmd_urls
}

cmd_destroy() {
  need kubectl; need terraform
  confirm "This deletes the MCP server, its Ingress (if any), and runs 'terraform destroy' — deletes the EKS cluster and everything in it."
  kubectl delete -f "$K8S_DIR/mcp-server/ingress.yaml" --ignore-not-found
  make -C "$REPO_ROOT" mcp-undeploy-aws || true
  (cd "$TF_DIR" && terraform destroy)
}

case "${1:-}" in
  check)         cmd_check ;;
  infra)         cmd_infra ;;
  kubeconfig)    cmd_kubeconfig ;;
  observability) cmd_observability ;;
  mcp-server)    cmd_mcp_server ;;
  mcp-ingress)   cmd_mcp_ingress ;;
  urls)          cmd_urls ;;
  all)           cmd_all ;;
  destroy)       cmd_destroy ;;
  *) die "Usage: $0 {check|infra|kubeconfig|observability|mcp-server|mcp-ingress|urls|all|destroy} [-y|--yes]" ;;
esac
