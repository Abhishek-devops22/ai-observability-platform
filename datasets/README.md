# Datasets

`schema.py` defines the canonical telemetry record (README.md "Dataset
Schema") shared by `ai-engine/anomaly_detection`, `ai-engine/prediction`,
and the notebooks.

- `sample_telemetry.csv` — a small (300-row) tracked fixture for quick
  local testing/demos.
- `generated/` — larger generated datasets (gitignored — regenerate
  rather than commit).

```bash
python3 generate_synthetic_dataset.py --rows 5000 --out generated/telemetry.csv
```

Once real OTel-collected metrics are flowing (Phase 2/3), replace this
generator with an export job that pulls from Prometheus/Loki into the
same schema — `ai-engine/anomaly_detection` and `ai-engine/prediction`
don't care where the CSV came from, only that the columns match.
