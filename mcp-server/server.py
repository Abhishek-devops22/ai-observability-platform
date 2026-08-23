"""AI Observability Platform — MCP Server.

Exposes Kubernetes + observability (Loki/Prometheus/Tempo) as tools an
LLM can call to investigate and (optionally) remediate incidents. See
README.md "Phase 4 — MCP Server" for the tool table and example flow.

Run:
    python server.py                      # stdio transport (for MCP clients / Claude Desktop)
    TRANSPORT=streamable-http python server.py   # HTTP transport
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from config import settings
from tools import (
    describe_pod,
    get_events,
    get_logs,
    get_metrics,
    get_traces,
    list_failed_pods,
    restart_deployment,
    scale_deployment,
)

mcp = MCPServer(
    name="ai-observability-platform",
    instructions=(
        "Tools for investigating Kubernetes incidents: query logs (Loki), "
        "metrics (Prometheus), and traces (Tempo); inspect pod/deployment "
        "health; and, only when explicitly enabled, apply remediations "
        "(restart or scale a deployment). Prefer read-only tools first — "
        "build a root-cause hypothesis from logs/metrics/traces/events "
        "before recommending or taking a mutating action."
    ),
)

# Read-only investigation tools
mcp.add_tool(get_logs)
mcp.add_tool(get_metrics)
mcp.add_tool(get_traces)
mcp.add_tool(get_events)
mcp.add_tool(describe_pod)
mcp.add_tool(list_failed_pods)

# Mutating remediation tools (no-op unless ALLOW_MUTATIONS=true — see config.py)
mcp.add_tool(restart_deployment)
mcp.add_tool(scale_deployment)


def main() -> None:
    if settings.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=settings.http_host, port=settings.http_port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
