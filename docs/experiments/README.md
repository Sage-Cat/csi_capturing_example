# Experiment Framework Guide

Date: 2026-03-02

## Current State Summary

Before this refactor, the repository had:

- shared CSI parse/capture primitives (`csi_capture/parser.py`, `csi_capture/capture.py`)
- config-driven capture for `distance` and `angle` (`csi_capture/experiment.py`)
- distance model/evaluation logic embedded in a monolithic analysis script (`tools/analyze_wifi_distance_measurement.py`)
- no reusable capture/train/eval framework for introducing new experiment types

## Target Architecture

### Core framework modules

- `csi_capture/core/device.py`
  - serial device listing/resolution/access checks
- `csi_capture/core/dataset.py`
  - run metadata schema validation
  - adapter reader for packet files (`.jsonl`/`.csv`)
- `csi_capture/core/features.py`
  - CSI I/Q amplitude conversion
  - windowed feature extraction (mean/var/RMS/entropy)
- `csi_capture/core/models.py`
  - model factory and model artifact save/load
- `csi_capture/core/evaluation.py`
  - classification metrics + confusion matrix + per-run summary

### Experiment modules

- `csi_capture/experiments/static_sign_v1.py`
  - capture/train/eval implementation for static sign classification
- `csi_capture/experiments/distance.py`
  - compatibility adapter to existing distance capture config runner

### Unified CLI

- `csi_capture/cli.py`
- wrapper: `tools/exp`
- subcommands:
  - `capture`
  - `train`
  - `eval`
  - `list-devices`
  - `validate-config`
  - `distance` (compatibility adapter)

## Data Model

## static_sign_v1 run folder layout

```text
data/experiments/
  static_sign_v1/
    <dataset_id>/
      <label>/
        run_<run_id>/
          metadata.json
          frames.jsonl
```

### `metadata.json` schema

Required fields:

- `schema_version` (int, currently `1`)
- `experiment_name` (`static_sign_v1`)
- `label` (`baseline` or `hands_up`)
- `run_id` (string)
- `device` (string, `esp32_c3`)
- `serial_dev` (selected serial path)
- `start_time` (UTC ISO-8601)
- `end_time` (UTC ISO-8601)
- `sampling_params` (object: baud, timeout, duration/packet budget)

Optional fields:

- `subject_id`
- `environment_id`
- `notes`
- `serial_realpath`
- `records_captured`

### `frames.jsonl` record fields

Each row includes raw packet values:

- `timestamp`, `rssi`, `csi`, `esp_timestamp`, `mac`
- run labels/tags merged at capture time (`experiment_name`, `label`, `run_id`, optional subject/environment)

## CLI Workflows

### Device helpers

```bash
./tools/exp --list-devices
# or
./tools/exp list-devices
```

### Capture (`static_sign_v1`)

```bash
./tools/exp capture --experiment static_sign_v1 --label hands_up --runs 5 --duration 20s --device /dev/esp32_csi
./tools/exp capture --experiment static_sign_v1 --label baseline --runs 5 --duration 20s
```

Device selection precedence:

1. `--device`
2. env var `CSI_CAPTURE_DEVICE` (or `ESP32_CSI_DEVICE`)
3. default `/dev/esp32_csi`

Startup always prints selected device and resolved realpath.

Dry-run serial probe:

```bash
./tools/exp capture --experiment static_sign_v1 --dry-run-packets 5 --dry-run-timeout 10s
```

### Train (`static_sign_v1`)

```bash
./tools/exp train \
  --experiment static_sign_v1 \
  --dataset data/experiments/static_sign_v1/<dataset_id> \
  --model svm_linear \
  --window 1s \
  --overlap 0.5 \
  --artifact artifacts/static_sign_v1/<stamp>/svm_linear.pkl
```

Supported baseline models:

- `svm_linear`
- `logreg`

### Eval (`static_sign_v1`)

```bash
./tools/exp eval \
  --experiment static_sign_v1 \
  --dataset data/experiments/static_sign_v1/<dataset_id> \
  --model artifacts/static_sign_v1/<stamp>/svm_linear.pkl \
  --report out/static_sign_v1/report.json
```

Report JSON includes:

- `accuracy`, `precision`, `recall`, `f1`
- `confusion_matrix`
- `per_run_summary`

### Compatibility (distance)

Existing distance commands remain unchanged:

- `python3 -m csi_capture.experiment distance --config docs/configs/distance_capture.sample.json`
- `scripts/run_rx_laptop.sh ...`
- `tools/analyze_wifi_distance_measurement.py ...`

New compatibility alias:

```bash
./tools/exp distance --config docs/configs/distance_capture.sample.json
```

## How To Add A New Experiment Type

1. Create module `csi_capture/experiments/<name>.py` implementing:
   - dataset capture routine
   - feature-table builder
   - train/eval functions
   - config validator
2. Reuse shared primitives from `csi_capture/core/*`.
3. Register CLI command handling in `csi_capture/cli.py`.
4. Add sample config(s) under `docs/configs/`.
5. Add tests under `tests/` for:
   - schema validation
   - feature shape and parsing
   - CLI smoke and config validation

## Verification Steps

1. `python3 -m unittest discover -s tests -p 'test_*.py' -v`
2. `./tools/exp --help`
3. `./tools/exp --list-devices`
4. `./tools/exp capture --experiment static_sign_v1 --dry-run-packets 5 --dry-run-timeout 10s --device /dev/esp32_csi`
5. `./tools/exp validate-config --experiment static_sign_v1 --mode capture --config docs/configs/static_sign_v1.capture.sample.json`

Execution logs are recorded in:

- `docs/experiments/verification_static_sign_v1.md`

Two-laptop execution reference:

- `docs/experiments/static_sign_v1_two_laptop_workflow.md`

## Release Notes

- Added reusable core framework modules for device/dataset/features/models/evaluation.
- Added new experiment type `static_sign_v1` (binary `baseline` vs `hands_up`).
- Added unified CLI wrapper `tools/exp` with `capture/train/eval` plus `--list-devices` and dry-run serial mode.
- Added schema/feature/CLI smoke tests.
- Preserved existing distance-estimation workflow and commands.
