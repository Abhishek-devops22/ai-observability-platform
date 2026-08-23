"""restart_deployment, scale_deployment — the platform's two mutating
tools. Both are gated behind config.settings.allow_mutations (default
False), per the README's "Read-only MCP access by default" security
posture. In production these should also sit behind the Slack-approval /
Argo Workflow gate described in the README's remediation flow, rather
than being invoked directly by the LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone

from config import settings
from tools._clients import apps_v1


class MutationsDisabledError(RuntimeError):
    pass


def _require_mutations_allowed(action: str) -> None:
    if not settings.allow_mutations:
        raise MutationsDisabledError(
            f"Refusing to {action}: ALLOW_MUTATIONS is disabled. "
            "This MCP server is read-only by default — see mcp-server/config.py."
        )


def restart_deployment(namespace: str, name: str) -> dict:
    """Trigger a rolling restart of a Deployment (equivalent to
    `kubectl rollout restart deployment/<name>`), by patching a
    restart-timestamp annotation on the pod template."""
    _require_mutations_allowed("restart_deployment")

    apps = apps_v1()
    now = datetime.now(timezone.utc).isoformat()
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                }
            }
        }
    }
    apps.patch_namespaced_deployment(name=name, namespace=namespace, body=patch)

    return {"action": "restart_deployment", "namespace": namespace, "deployment": name, "restarted_at": now}


def scale_deployment(namespace: str, name: str, replicas: int) -> dict:
    """Scale a Deployment to `replicas` (horizontal scaling remediation
    for High CPU / High Latency incidents)."""
    _require_mutations_allowed("scale_deployment")
    if replicas < 0:
        raise ValueError("replicas must be >= 0")

    apps = apps_v1()
    apps.patch_namespaced_deployment_scale(
        name=name,
        namespace=namespace,
        body={"spec": {"replicas": replicas}},
    )

    return {"action": "scale_deployment", "namespace": namespace, "deployment": name, "replicas": replicas}
