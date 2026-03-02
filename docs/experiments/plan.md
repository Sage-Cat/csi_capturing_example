# Gate 4 Implementation Plan

Date: 2026-03-02

## Strategy

Implement additive modules and adapters first, then wire a new CLI, then add `static_sign_v1`, then verify. Existing distance scripts/commands remain untouched.

## Step-by-step Plan

1. Add shared core modules (`csi_capture/core/*`).
Files:
- `csi_capture/core/__init__.py`
- `csi_capture/core/device.py`
- `csi_capture/core/dataset.py`
- `csi_capture/core/features.py`
- `csi_capture/core/models.py`
- `csi_capture/core/evaluation.py`
Changes:
- Device resolution/listing/error messaging
- Run metadata schema validator
- Legacy/new dataset adapter loader
- Windowed amplitude feature extraction
- Model persistence helpers
- Classification metric/report helpers

2. Add experiment modules.
Files:
- `csi_capture/experiments/__init__.py`
- `csi_capture/experiments/static_sign_v1.py`
- `csi_capture/experiments/distance.py`
Changes:
- `static_sign_v1` capture/train/eval wiring
- Distance adapter delegating to existing `csi_capture.experiment` flow

3. Add unified CLI and executable wrapper.
Files:
- `csi_capture/cli.py`
- `tools/exp`
Changes:
- Subcommands: `capture`, `train`, `eval`, `list-devices`, `distance`
- Device resolution precedence: flag > env > default
- `--dry-run-packets` to open serial/read N packets and exit

4. Add config templates and docs.
Files:
- `docs/configs/static_sign_v1.capture.sample.json`
- `docs/configs/static_sign_v1.train.sample.json`
- `docs/experiments/README.md`
Changes:
- Reproducible command recipes and metadata schema documentation

5. Add/update tests.
Files:
- `tests/test_dataset_schema.py`
- `tests/test_features.py`
- `tests/test_cli.py`
- (keep existing parser/capture/experiment tests unchanged)
Changes:
- Schema validation tests
- Feature shape test for window extraction
- CLI `--help` and config validation smoke tests

6. Execute verification and capture logs.
Files:
- `docs/experiments/verification_static_sign_v1.md`
Changes:
- Commands run
- Key outputs and pass/fail
- Known limitations (if hardware unavailable during CI-like run)

7. Final checklist and release notes.
Files:
- `docs/experiments/requirements.md` (update with PASS/FAIL)
- `docs/experiments/README.md` (release notes section)

## Migration Strategy

- No destructive migration of existing distance datasets.
- New `static_sign_v1` uses separate root under `data/experiments/static_sign_v1/...`.
- Adapter reader supports old packet files and new run-structured datasets.
- Legacy distance scripts continue unchanged; new CLI adds optional adapter aliases.

## Compatibility Notes

- Keep `csi_capture.capture` parser/capture API stable for existing tests and scripts.
- Keep `csi_capture.experiment` behavior unchanged for distance/angle config captures.
- Additive CLI (`tools/exp`) avoids changing existing invocation paths.
- Device default remains `/dev/esp32_csi`; explicit realpath and permission guidance improves operator UX.

## Risk Controls

- Prefer additive files over modifying proven capture code.
- Introduce unit tests for new schema/features/CLI before verification run.
- Use dry-run serial probe to validate device open path without requiring long captures.
