from remediation.engine import recommend, recommend_for_pod


def test_recommend_matches_kubernetes_event_reason():
    rec = recommend("CrashLoopBackOff")
    assert rec.action == "restart_deployment"
    assert rec.auto_approvable is True


def test_recommend_matches_rca_issue_alias_case_insensitively():
    rec = recommend("Memory Leak / OOM Risk")
    assert rec.incident == "OOMKilled"
    assert rec.auto_approvable is False


def test_recommend_returns_none_for_unknown_incident():
    assert recommend("SomeUnmappedReason") is None


def test_recommend_for_pod_deduplicates_and_skips_unknown_reasons():
    recs = recommend_for_pod(["CrashLoopBackOff", "CrashLoopBackOff", "SomethingUnknown", "OOMKilled"])
    assert [r.incident for r in recs] == ["CrashLoopBackOff", "OOMKilled"]
