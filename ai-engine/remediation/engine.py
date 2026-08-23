"""Remediation engine — maps an incident to a recommended action per
README.md "Phase 6 — Remediation Engine":

    CrashLoopBackOff   -> Restart Deployment
    OOMKilled          -> Increase Memory
    High CPU           -> Scale Replicas
    High Latency       -> Investigate DB
    ImagePullBackOff   -> Validate Registry Secret

This module only *recommends* — it does not call the MCP server's
mutating tools directly. The approval workflow (README: "AI
Recommendation -> Slack Approval -> Argo Workflow -> kubectl apply")
is intentionally a separate hop.
"""

from __future__ import annotations

from dataclasses import dataclass

RUNBOOK = {
    "CrashLoopBackOff": {
        "action": "restart_deployment",
        "description": "Restart Deployment",
        "auto_approvable": True,
    },
    "OOMKilled": {
        "action": "increase_memory_limit",
        "description": "Increase Memory",
        "auto_approvable": False,  # requires editing resource limits, not a simple retry
    },
    "HighCPU": {
        "action": "scale_deployment",
        "description": "Scale Replicas",
        "auto_approvable": True,
    },
    "HighLatency": {
        "action": "investigate_db",
        "description": "Investigate DB",
        "auto_approvable": False,
    },
    "ImagePullBackOff": {
        "action": "validate_registry_secret",
        "description": "Validate Registry Secret",
        "auto_approvable": False,
    },
    "ErrImagePull": {
        "action": "validate_registry_secret",
        "description": "Validate Registry Secret",
        "auto_approvable": False,
    },
}

# Free-text root-cause labels (e.g. from rca_agent.RCAResult.issue) that
# map onto a runbook key above.
_ISSUE_ALIASES = {
    "memory leak / oom risk": "OOMKilled",
    "cpu saturation": "HighCPU",
    "latency degradation": "HighLatency",
    "database connection pool exhausted": "HighLatency",
}


@dataclass
class Recommendation:
    incident: str
    action: str
    description: str
    auto_approvable: bool


def recommend(incident_reason: str) -> Recommendation | None:
    """Look up the recommended remediation for a Kubernetes event reason
    (e.g. "CrashLoopBackOff") or an RCA agent issue string. Returns None
    if nothing in the runbook matches.
    """
    key = incident_reason if incident_reason in RUNBOOK else _ISSUE_ALIASES.get(incident_reason.lower())
    if key is None:
        return None

    entry = RUNBOOK[key]
    return Recommendation(
        incident=key,
        action=entry["action"],
        description=entry["description"],
        auto_approvable=entry["auto_approvable"],
    )


def recommend_for_pod(reasons: list[str]) -> list[Recommendation]:
    """Given the `reasons` list from
    mcp_server.tools.kubernetes.list_failed_pods(), return every
    matching recommendation (deduplicated, runbook order)."""
    seen = set()
    out = []
    for reason in reasons:
        rec = recommend(reason)
        if rec and rec.incident not in seen:
            seen.add(rec.incident)
            out.append(rec)
    return out
