"""get_events — Kubernetes Events for a namespace/object."""

from __future__ import annotations

from tools._clients import core_v1


def get_events(
    namespace: str,
    object_name: str | None = None,
    limit: int = 50,
) -> dict:
    """List recent Kubernetes Events in a namespace, optionally filtered
    to those involving a specific object (pod, deployment, node, ...).
    """
    v1 = core_v1()
    field_selector = None
    if object_name:
        field_selector = f"involvedObject.name={object_name}"

    resp = v1.list_namespaced_event(
        namespace=namespace,
        field_selector=field_selector,
        limit=limit,
    )

    events = [
        {
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "involved_object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "count": e.count,
            "last_timestamp": e.last_timestamp.isoformat() if e.last_timestamp else None,
        }
        for e in resp.items
    ]
    events.sort(key=lambda e: e["last_timestamp"] or "", reverse=True)

    return {"namespace": namespace, "object": object_name, "count": len(events), "events": events}
