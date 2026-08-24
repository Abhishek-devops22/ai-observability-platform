# Kubernetes Observability Stack

Helm values for every component in Phase 2/3. Apply in this order once
`kubectl` points at the cluster (`terraform output configure_kubectl`).

```bash
kubectl apply -f namespaces/namespaces.yaml

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# AWS Load Balancer Controller — install before applying grafana/ingress.yaml
# or kubernetes/mcp-server/ingress.yaml, since those need it running to get
# reconciled. Role ARN from `terraform output lb_controller_role_arn`.
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=<cluster_name> \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=<lb_controller_role_arn>

# Metrics + Alertmanager
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -n observability -f prometheus/values.yaml

kubectl create secret generic alertmanager-config \
  -n observability --from-file=alertmanager.yaml=alertmanager/alertmanager.yaml

# Logs — backed by the bundled MinIO subchart (loki/values.yaml sets
# minio.enabled: true). MinIO's root credentials are deliberately NOT in
# that file (same reasoning as alertmanager-config below) — generate
# them at install time. See loki/values.yaml's header comment for why
# minio.existingSecret/env-var expansion doesn't work for this chart's
# minio integration and what that means for where the password ends up.
helm upgrade --install loki grafana/loki -n observability -f loki/values.yaml \
  --set minio.rootUser=loki-minio-admin \
  --set minio.rootPassword="$(openssl rand -base64 24)"

# Traces
# grafana/tempo (monolithic) prints "this chart is deprecated" — still
# installs fine, but Grafana's long-term recommendation is
# grafana/tempo-distributed for production. Not switched here.
helm upgrade --install tempo grafana/tempo -n observability -f tempo/values.yaml

# Collector (must come after the above so its exporters resolve)
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n observability -f otel-collector/values.yaml

# Dashboards
helm upgrade --install grafana grafana/grafana -n observability -f grafana/values.yaml \
  --set-file dashboards.default.executive.json=../dashboards/executive-dashboard.json \
  --set-file dashboards.default.sre.json=../dashboards/sre-dashboard.json \
  --set-file dashboards.default.ai.json=../dashboards/ai-dashboard.json

# Ingress — internal-facing ALB (VPC-only, not public internet); see
# grafana/ingress.yaml's header comment before changing that.
kubectl apply -f grafana/ingress.yaml
```

Get the Grafana admin password:

```bash
kubectl get secret grafana -n observability -o jsonpath="{.data.admin-password}" | base64 -d
```

Get the Grafana URL (takes a minute or two after `apply` for the ALB
controller to provision it):

```bash
kubectl get ingress grafana -n observability -o jsonpath="{.status.loadBalancer.ingress[0].hostname}"
```
