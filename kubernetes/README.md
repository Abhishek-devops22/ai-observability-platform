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

# Metrics + Alertmanager
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -n observability -f prometheus/values.yaml

kubectl create secret generic alertmanager-config \
  -n observability --from-file=alertmanager.yaml=alertmanager/alertmanager.yaml

# Logs
helm upgrade --install loki grafana/loki -n observability -f loki/values.yaml

# Traces
helm upgrade --install tempo grafana/tempo -n observability -f tempo/values.yaml

# Collector (must come after the above so its exporters resolve)
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n observability -f otel-collector/values.yaml

# Dashboards
helm upgrade --install grafana grafana/grafana -n observability -f grafana/values.yaml \
  --set-file dashboards.default.executive.json=../dashboards/executive-dashboard.json \
  --set-file dashboards.default.sre.json=../dashboards/sre-dashboard.json \
  --set-file dashboards.default.ai.json=../dashboards/ai-dashboard.json

# AWS Load Balancer Controller (role ARN from `terraform output lb_controller_role_arn`)
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=<cluster_name> \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=<lb_controller_role_arn>
```

Get the Grafana admin password:

```bash
kubectl get secret grafana -n observability -o jsonpath="{.data.admin-password}" | base64 -d
```
