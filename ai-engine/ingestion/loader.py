"""Log ingestion: raw logs -> cleaned, chunked LogRecords ready for
embedding. See README.md "Phase 5 — 1. Log Ingestion" for the pipeline
this implements (Raw Logs -> Cleaning -> Chunking -> Embeddings -> Vector DB).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class LogRecord:
    """A single, cleaned log line plus the metadata the vector store
    indexes on (matches the schema documented in the root README)."""

    text: str
    timestamp: datetime
    namespace: str
    pod: str
    service: str
    severity: str = "INFO"

    def metadata(self) -> dict:
        return {
            "namespace": self.namespace,
            "pod": self.pod,
            "service": self.service,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


def clean_line(raw: str) -> str:
    """Strip ANSI color codes and collapse whitespace. Returns "" for
    lines that are empty after cleaning, so callers can filter them out."""
    text = _ANSI_ESCAPE.sub("", raw)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


_SEVERITY_PATTERN = re.compile(r"\b(FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE)\b", re.IGNORECASE)


def infer_severity(line: str) -> str:
    match = _SEVERITY_PATTERN.search(line)
    if not match:
        return "INFO"
    sev = match.group(1).upper()
    return "WARN" if sev == "WARNING" else sev


def load_records(
    raw_lines: list[str],
    namespace: str,
    pod: str,
    service: str,
    timestamp: datetime,
) -> list[LogRecord]:
    """Clean a batch of raw log lines into LogRecords, dropping blanks."""
    records = []
    for raw in raw_lines:
        cleaned = clean_line(raw)
        if not cleaned:
            continue
        records.append(
            LogRecord(
                text=cleaned,
                timestamp=timestamp,
                namespace=namespace,
                pod=pod,
                service=service,
                severity=infer_severity(cleaned),
            )
        )
    return records


def chunk_records(records: list[LogRecord], chunk_size: int = 20) -> list[list[LogRecord]]:
    """Group consecutive log records into fixed-size chunks for embedding
    (embedding whole windows of context reads better than single lines)."""
    return [records[i : i + chunk_size] for i in range(0, len(records), chunk_size)]
