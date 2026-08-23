"""Unit tests for the MCP tool functions. Backend HTTP calls and the
Kubernetes API client are mocked — these do not require a live cluster
or observability stack."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tools import kubernetes as k8s_tools
from tools import logs as logs_tools
from tools import metrics as metrics_tools
from tools import remediation


# --- logs.get_logs ------------------------------------------------------

def test_get_logs_builds_selector_and_parses_streams(monkeypatch):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"namespace": "prod", "pod": "payment-123"},
                    "values": [["1700000000000000000", "OOMKilled"]],
                }
            ]
        }
    }
    fake_client = MagicMock()
    fake_client.get.return_value = fake_response
    monkeypatch.setattr(logs_tools, "http_client", lambda: fake_client)

    result = logs_tools.get_logs(namespace="prod", pod="payment", contains="OOM")

    assert result["count"] == 1
    assert result["logs"][0]["line"] == "OOMKilled"
    assert 'namespace="prod"' in result["query"]
    assert 'pod=~"payment.*"' in result["query"]
    assert "|= `OOM`" in result["query"]


# --- metrics.get_metrics -------------------------------------------------

def test_get_metrics_instant_query_hits_query_endpoint(monkeypatch):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"data": {"result": []}}
    fake_client = MagicMock()
    fake_client.get.return_value = fake_response
    monkeypatch.setattr(metrics_tools, "http_client", lambda: fake_client)

    result = metrics_tools.get_metrics("up")

    assert result["type"] == "instant"
    called_url = fake_client.get.call_args.args[0]
    assert called_url.endswith("/api/v1/query")


def test_get_metrics_range_query_hits_query_range_endpoint(monkeypatch):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"data": {"result": []}}
    fake_client = MagicMock()
    fake_client.get.return_value = fake_response
    monkeypatch.setattr(metrics_tools, "http_client", lambda: fake_client)

    result = metrics_tools.get_metrics("up", since_minutes=5)

    assert result["type"] == "range"
    called_url = fake_client.get.call_args.args[0]
    assert called_url.endswith("/api/v1/query_range")


# --- kubernetes.list_failed_pods -----------------------------------------

def _fake_pod(name, phase="Running", waiting_reason=None, restart_count=0):
    container_status = SimpleNamespace(
        state=SimpleNamespace(
            waiting=SimpleNamespace(reason=waiting_reason, message="x") if waiting_reason else None,
            terminated=None,
            running=None,
        ),
        restart_count=restart_count,
    )
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, namespace="prod"),
        spec=SimpleNamespace(node_name="node-1"),
        status=SimpleNamespace(
            phase=phase,
            start_time="2026-01-01T00:00:00Z" if phase != "Pending" else None,
            container_statuses=[container_status],
        ),
    )


def test_list_failed_pods_flags_crash_loop_backoff(monkeypatch):
    healthy = _fake_pod("healthy-pod")
    crashing = _fake_pod("payment-123", waiting_reason="CrashLoopBackOff")

    fake_v1 = MagicMock()
    fake_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[healthy, crashing])
    monkeypatch.setattr(k8s_tools, "core_v1", lambda: fake_v1)

    result = k8s_tools.list_failed_pods(namespace="prod")

    assert result["count"] == 1
    assert result["pods"][0]["pod"] == "payment-123"
    assert "CrashLoopBackOff" in result["pods"][0]["reasons"]


# --- remediation guardrail -------------------------------------------------

def test_restart_deployment_refuses_when_mutations_disabled(monkeypatch):
    monkeypatch.setattr(remediation.settings, "allow_mutations", False)

    with pytest.raises(remediation.MutationsDisabledError):
        remediation.restart_deployment(namespace="prod", name="payment-service")


def test_scale_deployment_succeeds_when_mutations_enabled(monkeypatch):
    monkeypatch.setattr(remediation.settings, "allow_mutations", True)
    fake_apps = MagicMock()
    monkeypatch.setattr(remediation, "apps_v1", lambda: fake_apps)

    result = remediation.scale_deployment(namespace="prod", name="payment-service", replicas=5)

    assert result["replicas"] == 5
    fake_apps.patch_namespaced_deployment_scale.assert_called_once()
