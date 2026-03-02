# Gate 2 Architecture Proposal

Date: 2026-03-02

## Goals

- Introduce a reusable experiment framework without breaking current distance estimation workflows.
- Add `static_sign_v1` binary classification (`baseline`, `hands_up`).
- Standardize capture/train/eval entrypoints and dataset schema.

## Proposed Modular Structure

### Code layout

- `csi_capture/core/`
  - Shared building blocks used by all experiments.
  - Modules:
    - `device.py`: device resolution/listing/access checks
    - `dataset.py`: run metadata schema validation + dataset loading/adapter
    - `features.py`: shared CSI amplitude + window feature extraction
    - `models.py`: model factory/save/load helpers
    - `evaluation.py`: metrics, confusion matrix, per-run summaries
- `csi_capture/experiments/`
  - Experiment-specific rules and pipelines.
  - `static_sign_v1.py`: labels/config defaults + train/eval data preparation
  - `distance.py`: compatibility adapter to existing distance flow
- `csi_capture/cli.py`
  - Unified command backend with subcommands `capture`, `train`, `eval`, `list-devices`.
- `tools/exp`
  - Thin executable wrapper calling `python3 -m csi_capture.cli`.

### Data layout

- New framework dataset root (default):
  - `data/experiments/<experiment_name>/<dataset_id>/<label>/run_<run_id>/`
- Per-run files:
  - `frames.jsonl` (raw parsed packet rows)
  - `metadata.json` (schema-validated run metadata)

### Backward compatibility

- Keep existing commands and scripts unchanged:
  - `python -m csi_capture.experiment distance --config ...`
  - `scripts/run_rx_laptop.sh`
  - `tools/analyze_wifi_distance_measurement.py`
- Add adapter path in new CLI:
  - `./tools/exp distance --config ...` delegates to existing config runner.
- Dataset compatibility:
  - adapter reader in `core/dataset.py` can read new run schema and legacy JSONL packet files.

## Runtime Flow (New CLI)

### Capture

1. Resolve serial device in precedence order: CLI flag > env var > default (`/dev/esp32_csi`).
2. Print selected path and resolved realpath.
3. Check existence/access; on permission error print `dialout` guidance.
4. For each run:
   - open serial stream
   - parse `CSI_DATA` rows
   - write `frames.jsonl`
   - write `metadata.json` with start/end timestamps and capture params

### Train

1. Load dataset from run folders + validate metadata.
2. Build windowed features (mean/variance/RMS/entropy on CSI amplitude).
3. Group split by run id.
4. Train baseline classifier (`svm_linear` or `logreg`).
5. Save model artifact + training metrics JSON.

### Eval

1. Load model artifact.
2. Recompute features from dataset.
3. Predict and produce:
   - accuracy/precision/recall/F1
   - confusion matrix
   - per-run summary
4. Write report JSON.

## ASCII Diagram

```text
                   +-------------------+
                   |    tools/exp      |
                   | capture/train/eval|
                   +---------+---------+
                             |
                             v
                   +-------------------+
                   |  csi_capture.cli  |
                   +---------+---------+
                             |
          +------------------+------------------+
          |                                     |
          v                                     v
+----------------------+            +--------------------------+
| csi_capture/core/*   |            | csi_capture/experiments/*|
| device,dataset,      |            | static_sign_v1,distance  |
| features,models,eval |            | rules + adapters         |
+----------+-----------+            +------------+-------------+
           |                                     |
           +------------------+------------------+
                              |
                              v
               +-------------------------------+
               | data/experiments/<exp>/<id>/  |
               | <label>/run_<id>/{frames,meta}|
               +-------------------------------+
```

# Gate 3 Design Validation

## Validation Matrix

1. Shared capture subsystem: `PASS`
- Centralized device + capture flow in `core` modules.

2. Shared dataset schema + storage: `PASS`
- Run-level `metadata.json` schema and consistent run folder layout.

3. Shared feature/model/eval pipeline: `PASS`
- `core/features.py`, `core/models.py`, `core/evaluation.py` reused by experiment modules.

4. `static_sign_v1` binary experiment support: `PASS`
- Dedicated experiment module with labels and train/eval implementation.

5. CLI capture/train/eval + list devices: `PASS`
- Provided by `tools/exp` + `csi_capture.cli`.

6. Device requirements and permissions UX: `PASS`
- Realpath print + explicit permission error guidance.

7. Backward compatibility for distance workflow: `PASS`
- Existing scripts untouched + alias/adapter command in new CLI.

8. Migration/adapter for schema coexistence: `PASS`
- Adapter reader can ingest both new run schema and legacy packet files.

9. Reproducibility/testability: `PASS`
- Metadata includes run parameters/timestamps; CLI and schema validation are unit-testable.

## Outcome

Design satisfies all mapped requirements with minimal-risk, additive changes and no destructive migration.
