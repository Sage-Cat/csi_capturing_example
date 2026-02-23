# Repository Organization Guide

This repository is organized for a repeated capture-analysis cycle with multiple students.

## Tracked in Git

- `csi_capture/`: reusable capture/parser Python code.
- `scripts/`: operational shell scripts (`run_tx_laptop.sh`, `run_rx_laptop.sh`).
- `tools/`: analysis scripts for RSSI/CSI.
- `tests/`: unit tests.
- `docs/`: notes, workflow, and methodology.
- `data/`: small reusable sample files only.
- `.vscode.template/`: shared VS Code defaults.

## Local Only (Git-Ignored)

- `.vscode/`: each student's personal IDE settings/tasks copy.
- `experiments/`: raw experiment runs and metadata.
- `out/`: generated figures/tables/reports.
- `out_*`: legacy output folders.
- build and temporary artifacts.

## Capture to Analysis Flow

1. Capture raw packets using `scripts/run_rx_laptop.sh`.
2. Raw logs are stored under `experiments/<exp_id>/...`.
3. Run analysis scripts from `tools/` with `--data_dir experiments/<exp_id>`.
4. Reports/figures/tables are generated under `out/`.

This keeps source code clean while allowing unlimited local experiments.
