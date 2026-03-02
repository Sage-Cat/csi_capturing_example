# Gate 1 Requirements Mapping

Date: 2026-03-02

## Explicit Requirements Checklist

Legend:
- `EXISTS`: already implemented in repo
- `MISSING`: not implemented yet
- `PARTIAL`: partially present but needs extension/refactor

1. Reusable experiment framework with shared core (`capture`, dataset schema/storage, feature pipeline, models, eval/reporting).
Status: `MISSING`
Notes: capture and analysis exist, but analysis is script-specific and not frameworkized.

2. New experiment type `static_sign_v1` for binary classification `{baseline, hands_up}`.
Status: `MISSING`

3. Do not break existing distance-estimation experiment.
Status: `EXISTS` (baseline today)
Notes: must preserve this during refactor.

4. CLI with subcommands for `capture`, `train`, `eval`.
Status: `MISSING`
Notes: current CLI is `python -m csi_capture.experiment` for capture-only distance/angle configs.

5. Device behavior:
   - default `/dev/esp32_csi`
   - override by CLI and env var
   - startup prints resolved realpath
   - permission denied message with dialout guidance
   - `--list-devices` helper (`/dev/esp32_csi`, `/dev/ttyACM*`, `/dev/ttyUSB*`)
Status: `PARTIAL`
Notes: default path + access checks exist; no list-devices helper, no env override in unified CLI, no mandatory resolved-path startup print.

6. Capture reproducibility:
   - stable timestamps
   - explicit `run_id`
Status: `PARTIAL`
Notes: timestamp + run_id exist in current code; not unified for new static-sign dataset layout yet.

7. static_sign_v1 capture dataset structure:
   - multiple runs per class
   - each run stores raw frames + metadata JSON
   - metadata fields: `experiment_name`, `label`, optional `subject_id`, optional `environment_id`, `device`, `serial_dev`, `start_time`, `end_time`, sampling params, notes
Status: `MISSING`

8. static_sign_v1 feature extraction:
   - per-window amplitude statistics: mean, variance, RMS, entropy
   - configurable window/overlap
Status: `MISSING`

9. static_sign_v1 model:
   - baseline linear SVM or logistic regression
   - save model artifact + JSON metrics
Status: `MISSING`

10. static_sign_v1 evaluation output:
   - accuracy, precision, recall, F1
   - confusion matrix
   - per-run summary
Status: `MISSING`

11. Tests:
   - parser tests
   - dataset schema validation
   - feature extraction output shape
   - CLI `--help` smoke
   - config validation smoke
Status: `PARTIAL`
Notes: parser tests exist; missing new schema/feature/CLI/config smoke tests for framework.

12. Backwards compatibility:
   - old distance scripts/commands still run
   - if schema changes, provide migration tool or adapter reader
Status: `PARTIAL`
Notes: distance pipeline works now; adapter needed for any new schema integration.

13. Verification artifact:
   - run commands (tests/lint if present/dry-run capture)
   - record outputs in `docs/experiments/verification_static_sign_v1.md`
Status: `MISSING`

14. Final review artifact:
   - checklist PASS/FAIL
   - release notes
Status: `MISSING`

## Existing Components to Reuse

- Packet parsing and capture stream:
  - `csi_capture/parser.py`
  - `csi_capture/capture.py`
- Config-driven capture runner:
  - `csi_capture/experiment.py`
- Distance analysis/modeling logic (for adapter compatibility):
  - `tools/analyze_wifi_distance_measurement.py`
- Existing tests:
  - `tests/test_parser.py`
  - `tests/test_capture.py`
  - `tests/test_experiment.py`

## Gate 7 Final PASS/FAIL Review

1. Reusable experiment framework with shared core. Final: `PASS`
2. New `static_sign_v1` binary experiment type. Final: `PASS`
3. Existing distance-estimation workflow preserved. Final: `PASS`
4. Unified CLI with `capture/train/eval`. Final: `PASS`
5. Device handling requirements (`/dev/esp32_csi`, override, realpath print, permission guidance, list-devices). Final: `PASS`
6. Reproducible capture with run_id and stable timestamps. Final: `PASS`
7. static_sign run layout + metadata fields. Final: `PASS`
8. Windowed amplitude features (mean/var/RMS/entropy). Final: `PASS`
9. Baseline model (linear SVM/logreg) + artifact + metrics JSON. Final: `PASS`
10. Eval output includes accuracy/precision/recall/F1/confusion/per-run summary. Final: `PASS`
11. Tests for parser/schema/features/CLI help/config validation. Final: `PASS`
12. Backward compatibility and adapter reader support. Final: `PASS`
13. Verification execution log in `docs/experiments/verification_static_sign_v1.md`. Final: `PASS`
14. Release notes included in docs. Final: `PASS`
