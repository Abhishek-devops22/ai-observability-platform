"""describe_pod, list_failed_pods — read-only Kubernetes inspection tools."""

from __future__ import annotations

from tools._clients import core_v1

_UNHEALTHY_WAITING_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "InvalidImageName",
}


def describe_pod(namespace: str, name: str) -> dict:
    """Return a structured equivalent of `kubectl describe pod`: phase,
    conditions, container statuses (including waiting/terminated reasons),
    and resource requests/limits."""
    v1 = core_v1()
    pod = v1.read_namespaced_pod(name=name, namespace=namespace)

    containers = []
    for status in pod.status.container_statuses or []:
        state_name, state_detail = _summarize_state(status.state)
        spec = next((c for c in pod.spec.containers if c.name == status.name), None)
        containers.append(
            {
                "name": status.name,
                "ready": status.ready,
                "restart_count": status.restart_count,
                "state": state_name,
                "state_detail": state_detail,
                "image": status.image,
                "resources": spec.resources.to_dict() if spec and spec.resources else None,
            }
        )

    conditions = [
        {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
        for c in (pod.status.conditions or [])
    ]

    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "node": pod.spec.node_name,
        "phase": pod.status.phase,
        "pod_ip": pod.status.pod_ip,
        "start_time": pod.status.start_time.isoformat() if pod.status.start_time else None,
        "conditions": conditions,
        "containers": containers,
    }


def list_failed_pods(namespace: str | None = None) -> dict:
    """List pods that are Failed, stuck Pending, or have an unhealthy
    container state (CrashLoopBackOff, ImagePullBackOff, OOMKilled, ...).
    Scans all namespaces if `namespace` is omitted.
    """
    v1 = core_v1()
    pods = (
        v1.list_namespaced_pod(namespace=namespace).items
        if namespace
        else v1.list_pod_for_all_namespaces().items
    )

    unhealthy = []
    for pod in pods:
        reasons = []

        if pod.status.phase in ("Failed",):
            reasons.append(pod.status.phase)
        elif pod.status.phase == "Pending" and pod.status.start_time is None:
            reasons.append("Pending")

        for status in pod.status.container_statuses or []:
            if status.state and status.state.waiting and status.state.waiting.reason in _UNHEALTHY_WAITING_REASONS:
                reasons.append(status.state.waiting.reason)
            if status.state and status.state.terminated and status.state.terminated.reason == "OOMKilled":
                reasons.append("OOMKilled")
            if status.restart_count and status.restart_count >= 5:
                reasons.append(f"HighRestartCount({status.restart_count})")

        if reasons:
            unhealthy.append(
                {
                    "namespace": pod.metadata.namespace,
                    "pod": pod.metadata.name,
                    "node": pod.spec.node_name,
                    "reasons": sorted(set(reasons)),
                }
            )

    return {"scope": namespace or "all-namespaces", "count": len(unhealthy), "pods": unhealthy}


def _summarize_state(state) -> tuple[str, dict | None]:
    if state is None:
        return "unknown", None
    if state.running:
        return "running", {"started_at": state.running.started_at.isoformat() if state.running.started_at else None}
    if state.waiting:
        return "waiting", {"reason": state.waiting.reason, "message": state.waiting.message}
    if state.terminated:
        return "terminated", {
            "reason": state.terminated.reason,
            "exit_code": state.terminated.exit_code,
            "message": state.terminated.message,
        }
    return "unknown", None
