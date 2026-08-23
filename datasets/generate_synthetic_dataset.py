#!/usr/bin/env python3
"""Generate a synthetic telemetry dataset matching schema.py / README.md
"Dataset Schema" — for local development and ai-engine model training
before real cluster telemetry is available.

Usage:
    python generate_synthetic_dataset.py --rows 5000 --out generated/telemetry.csv
    python generate_synthetic_dataset.py --rows 300 --out sample_telemetry.csv --seed 7
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from schema import COLUMNS

SERVICES = ["payment", "checkout", "inventory", "auth", "notification"]
NAMESPACES = ["prod", "staging"]


def generate_rows(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    for i in range(n):
        service = rng.choice(SERVICES)
        namespace = rng.choice(NAMESPACES)
        pod = f"{service}-{rng.randint(1, 20)}"
        timestamp = start + timedelta(minutes=i)

        # ~12% of rows simulate a pre-failure window: elevated resource
        # usage/latency/errors, matching the failure patterns the README
        # calls out (memory leak, high CPU, high latency, crash looping).
        is_failure_window = rng.random() < 0.12

        if is_failure_window:
            cause = rng.choice(["memory", "cpu", "latency", "restarts"])
            cpu = rng.uniform(0.85, 1.1) if cause == "cpu" else rng.uniform(0.2, 0.5)
            memory = rng.uniform(0.9, 1.15) if cause == "memory" else rng.uniform(0.3, 0.6)
            latency = rng.uniform(2500, 4500) if cause == "latency" else rng.uniform(100, 250)
            errors = rng.randint(10, 80)
            restarts = rng.randint(3, 9) if cause == "restarts" else rng.randint(0, 2)
            failed = True
        else:
            cpu = rng.uniform(0.1, 0.5)
            memory = rng.uniform(0.2, 0.6)
            latency = rng.uniform(50, 200)
            errors = rng.randint(0, 3)
            restarts = rng.randint(0, 1)
            failed = False

        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "namespace": namespace,
                "pod": pod,
                "cpu": round(cpu, 4),
                "memory": round(memory, 4),
                "latency": round(latency, 2),
                "errors": errors,
                "restarts": restarts,
                "failed": failed,
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=Path("generated/telemetry.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows(args.rows, args.seed)

    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    failure_rate = sum(r["failed"] for r in rows) / len(rows)
    print(f"Wrote {len(rows)} rows to {args.out} (failure rate: {failure_rate:.1%})")


if __name__ == "__main__":
    main()
