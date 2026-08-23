from datetime import datetime, timezone

from ingestion.loader import chunk_records, clean_line, infer_severity, load_records


def test_clean_line_strips_ansi_and_collapses_whitespace():
    raw = "\x1b[31mERROR\x1b[0m   connection    refused\n"
    assert clean_line(raw) == "ERROR connection refused"


def test_clean_line_blank_after_cleaning_is_empty_string():
    assert clean_line("   \x1b[0m  \n") == ""


def test_infer_severity_defaults_to_info():
    assert infer_severity("just a normal line") == "INFO"
    assert infer_severity("WARNING: disk almost full") == "WARN"
    assert infer_severity("FATAL crash") == "FATAL"


def test_load_records_drops_blank_lines_and_sets_metadata():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = ["ERROR db timeout", "   ", "INFO healthy"]

    records = load_records(raw, namespace="prod", pod="payment-123", service="payment", timestamp=ts)

    assert len(records) == 2
    assert records[0].severity == "ERROR"
    assert records[0].metadata()["namespace"] == "prod"


def test_chunk_records_splits_into_fixed_size_groups():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = load_records([f"line {i}" for i in range(45)], "prod", "pod", "svc", ts)

    chunks = chunk_records(records, chunk_size=20)

    assert [len(c) for c in chunks] == [20, 20, 5]
