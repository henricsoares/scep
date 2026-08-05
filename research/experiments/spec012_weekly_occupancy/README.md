# SPEC-012 External Weekly Occupancy Baseline

This directory contains a reproducible external research/batch job for the first SPEC-012
experiment. The Python module [`baseline.py`](baseline.py) is the source of truth. No notebook is
required to run, inspect or reproduce the pipeline.

The job demonstrates this boundary:

```text
SPEC-011 ANALYTICAL_OCCUPANCY CSV
    -> external weekday/hour baseline
    -> SPEC-012 publication JSON
    -> public SCEP Predictions API
```

SCEP does not train a model or run inference internally. The input is a SPEC-011
`ANALYTICAL_OCCUPANCY` CSV export, normally using the `RESEARCH` profile and hourly granularity.
The target is the SPEC-010 `effective_occupancy_rate`. The external job derives the owning
Facility's local weekday and hour with the configured IANA timezone, then calculates the arithmetic
mean for each weekday/hour group:

```text
E[effective_occupancy_rate | Facility-local weekday, Facility-local hour]
```

All 168 groups must be present. Missing, null, non-numeric, non-finite or out-of-range targets fail
the run; the job never silently imputes buckets. The output contains exactly 168 buckets in
weekday-major/hour-minor order and is compatible with
`POST /predictions/weekly-occupancy-publications`.

## Input preparation

Extract `data.csv` from the SPEC-011 artifact ZIP, or use the separately preserved `data.csv` from
the same export. Do not commit real exports. `research/datasets/` ignores local dataset files while
retaining its directory placeholders.

The Experiment 4 reference validation uses its 1,680-row, ten-week training export and 336-row,
two-week holdout export. Those preserved local artifacts are validation inputs only; their CSV,
ZIP, manifest and generated result files are not copied into this directory or committed.

## Run

From the repository root:

```bash
uv run --project backend python -m \
  research.experiments.spec012_weekly_occupancy.baseline \
  --training /path/to/training/data.csv \
  --holdout /path/to/holdout/data.csv \
  --output research/experiments/spec012_weekly_occupancy/runtime/prediction.json \
  --report research/experiments/spec012_weekly_occupancy/runtime/report.json \
  --scope-type FACILITY \
  --facility-id 00000000-0000-4000-8000-000000000001 \
  --timezone UTC \
  --model-name weekday-hour-effective-occupancy-mean \
  --model-version 1.0.0 \
  --external-run-id experiment-identifier \
  --dataset-export-id 00000000-0000-4000-8000-000000000002 \
  --training-data-from 2026-01-01T00:00:00Z \
  --training-data-to 2026-03-12T00:00:00Z \
  --generated-at 2026-03-12T12:00:00Z
```

`--holdout`, `--report` and `--dataset-export-id` are optional. For `STATION` or `CONNECTOR`
publication, select `--scope-type` and supply the corresponding `--station-id` and optional
`--connector-id` according to the SPEC-012 hierarchy. The dataset itself must represent that same
analytical scope; the job does not reconstruct or aggregate another scope.

The command writes `prediction.json`, optionally writes `report.json`, and prints the report to
standard output. It never publishes automatically.

## Evaluation report

When a holdout is supplied, every holdout row is evaluated against its local recurring bucket. The
report includes:

- training and holdout row counts;
- bucket count;
- training target mean;
- prediction mean, minimum and maximum;
- MAE and RMSE for the weekday/hour baseline;
- MAE and RMSE for the trivial global-training-mean baseline.

Training and holdout time windows must not overlap. The comparison is intentionally simple and
academically inspectable; this is not presented as a sophisticated machine-learning model.

## Publish and inspect

Publishing is a separate authorized action through the public SCEP API. Import
[`../../../docs/api/scep-spec012-insomnia.json`](../../../docs/api/scep-spec012-insomnia.json), copy
the generated payload into its `publication_payload` environment value, and use the collection to
publish and read the profile, history, current selection and point lookups. Recommendation requests
require an EVDriver token and current Connector publications for the candidate Connectors.

The same Python entry point could run in an external managed batch environment such as AWS Glue or
ECS with equivalent files and CLI metadata. No AWS Glue or ECS integration is implemented here.

## Validate

```bash
make research-test
make research-lint
make research-typecheck
```
