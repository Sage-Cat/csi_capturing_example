# ESP32 CSI/RSSI Experiment Toolkit

Toolkit for capturing ESP32 CSI packets, organizing experiment runs, and producing RSSI/CSI analysis reports.

Primary workflow:

- Laptop A (TX): flash/run `csi_send`
- Laptop B (RX): flash/run `csi_recv`, capture CSI stream, attach experiment metadata

## Repository Layout

```text
csi_capture/              # Python capture/parser/experiment modules
scripts/                  # Operational scripts (TX/RX, local setup)
tools/                    # Analysis scripts
tests/                    # Unit tests
docs/                     # Notes + config templates + architecture docs
experiments/              # Local raw runs (git-ignored except README/.gitkeep)
out/                      # Local generated figures/tables/reports (git-ignored except README/.gitkeep)
data/                     # Small reusable sample data only
.vscode.template/         # Tracked VS Code defaults copied to local .vscode/
```

`experiments/`, `out/`, build files, and `.vscode/` are intentionally ignored so students can run scripts locally without polluting git history.

## 1) System Dependencies (Both Laptops)

Linux (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y \
  git wget flex bison gperf python3 python3-pip python3-venv python3-serial \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
sudo usermod -a -G dialout $USER
```

Log out and log in again after adding `dialout`.

macOS (Homebrew):

```bash
brew install python cmake ninja ccache dfu-util libusb
python3 -m pip install -r requirements.txt
```

On macOS, serial ports are usually like `/dev/cu.usbmodem*` or `/dev/tty.usbmodem*`.

## 2) ESP-IDF + esp-csi Setup

```bash
mkdir -p ~/esp
cd ~/esp
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3
```

Optional helper alias:

```bash
echo "alias get_idf='. $HOME/esp/esp-idf/export.sh'" >> ~/.bashrc
source ~/.bashrc
```

Clone `esp-csi`:

```bash
cd ~/esp
git clone https://github.com/espressif/esp-csi.git
```

## 3) Project Setup

```bash
git clone git@github.com:Sage-Cat/csi_capturing_example.git
cd csi_capturing_example
python3 -m pip install -r requirements.txt
```

Optional local VS Code bootstrap:

```bash
./scripts/setup_vscode.sh
```

This copies tracked templates from `.vscode.template/` to your local ignored `.vscode/`.

## 4) Capture Commands

TX node:

```bash
./scripts/run_tx_laptop.sh
```

RX node:

```bash
./scripts/run_rx_laptop.sh \
  --port /dev/esp32_csi \
  --exp-id exp_2026_02_23_lab \
  --scenario LoS \
  --run-id 1 \
  --distance-m 1.0 \
  --max-records 2500
```

On macOS, pass explicit ports when needed, for example:

```bash
./scripts/run_tx_laptop.sh --port /dev/cu.usbmodem2101
./scripts/run_rx_laptop.sh --port /dev/cu.usbmodem1101 --exp-id exp_macos_test --scenario LoS --run-id 1 --distance-m 1.0 --max-records 200
```

By default, RX output is stored under `experiments/<exp_id>/...`.

New unified config-driven runner (distance + angle):

```bash
# Distance experiment from config
python3 -m csi_capture.experiment distance \
  --config docs/configs/distance_capture.sample.json

# Angle/AoA dataset capture from config
python3 -m csi_capture.experiment angle \
  --config docs/configs/angle_capture.sample.json

# Radial angle sweep around AP center: 0,45,...,315 with 2 runs
python3 -m csi_capture.experiment angle \
  --config docs/configs/angle_radial_45deg_2runs.sample.json
```

Config defaults use auto serial selection (`device.path: "auto"`), preferring `/dev/esp32_csi`
when available and falling back to detected serial candidates (`/dev/ttyACM*`, `/dev/cu.usbmodem*`, etc.).
`run_ids` can be set in config to execute multiple full sweeps in one command.
For cross-platform use (including macOS), angle configs now use `device.path: "auto"` and
you can always override from CLI:

```bash
python3 -m csi_capture.experiment angle \
  --config docs/configs/angle_radial_45deg_2runs.sample.json \
  --device auto
```

New experiment framework CLI (includes `static_sign_v1`):

```bash
# List serial candidates (includes /dev/esp32_csi symlink resolution)
./tools/exp --list-devices

# Dry-run: open serial and parse N CSI packets, then exit
./tools/exp capture --experiment static_sign_v1 --dry-run-packets 5 --dry-run-timeout 10s

# Capture static sign dataset
./tools/exp capture --experiment static_sign_v1 --label hands_up --runs 5 --duration 20s
./tools/exp capture --experiment static_sign_v1 --label baseline --runs 5 --duration 20s

# Protocol helper (baseline then hands_up with prompts)
./scripts/run_static_sign_protocol.sh \
  --device /dev/esp32_csi \
  --dataset-id 20260302_subject01_labA \
  --runs 5 \
  --duration 20s \
  --subject-id subject01 \
  --environment-id labA
```

Device selection precedence for `tools/exp capture`:

1. `--device`
2. env var `CSI_CAPTURE_DEVICE` (or `ESP32_CSI_DEVICE`)
3. `/dev/esp32_csi` if present, otherwise auto-detected serial candidate

For complete AP+RX two-laptop setup instructions, see:

- `docs/experiments/static_sign_v1_two_laptop_workflow.md`

## 5) Experiment Data Structure

Each captured row stores:

- `timestamp` (host Unix ms)
- `rssi`
- `csi` (I/Q integer array)
- `esp_timestamp`
- `mac`
- plus metadata tags such as `exp_id`, `experiment_type`, `run_id`, `trial_id`, `device_path`, scenario fields, and ground-truth (`distance_m` or `angle_deg`)

Example:

```json
{"timestamp":1700000000000,"rssi":-15,"csi":[1,-2,3,-4],"esp_timestamp":119050,"mac":"1a:00:00:00:00:00","exp_id":"exp_2026_02_23_lab","experiment_type":"angle","run_id":"1","trial_id":"angle_30deg_rep_001","device_path":"/dev/esp32_csi","scenario_tags":["LoS"],"angle_deg":30.0}
```

Layout:

- Legacy distance script layout (unchanged):
  - `experiments/<exp_id>/meta.json`
  - `experiments/<exp_id>/<scenario>/run_<run_id>/distance_<X>m.jsonl`
- Unified runner layout:
  - `experiments/<exp_id>/<experiment_type>/run_<run_id>/manifest.json`
  - `experiments/<exp_id>/<experiment_type>/run_<run_id>/trial_<trial_id>/capture.jsonl`

Every unified runner invocation writes a per-run `manifest.json` with config snapshot, git revision, device path, and trial summaries.

## 6) Analysis Commands

Distance measurement:

```bash
python3 tools/analyze_wifi_distance_measurement.py \
  --data_dir experiments/<exp_id> \
  --out_dir out/distance_measurement
```

Stability statistics:

```bash
python3 tools/analyze_wifi_stability_statistics.py \
  --data_dir experiments/<exp_id> \
  --out_dir out/stability_statistics
```

Angle dataset summary:

```bash
python3 tools/analyze_wifi_angle_dataset.py \
  --data_dir experiments/<exp_id>/angle \
  --out_dir out/angle_dataset
```

Outputs are written to `out/` and are git-ignored.

Static sign train/eval:

```bash
./tools/exp train \
  --experiment static_sign_v1 \
  --dataset data/experiments/static_sign_v1/<dataset_id> \
  --model svm_linear \
  --window 1s \
  --overlap 0.5

./tools/exp eval \
  --experiment static_sign_v1 \
  --dataset data/experiments/static_sign_v1/<dataset_id> \
  --model artifacts/static_sign_v1/<stamp>/svm_linear.pkl \
  --report out/static_sign_v1/report.json
```

## 7) Make Targets

```bash
make setup-vscode
make test
make tx-node PORT=/dev/ttyACM0
make rx-smoke PORT=/dev/ttyACM1 EXP_ID=exp_smoke
make experiment-distance DISTANCE_CONFIG=docs/configs/distance_capture.sample.json
make experiment-angle ANGLE_CONFIG=docs/configs/angle_radial_45deg_2runs.sample.json
make analyze-distance DATA_DIR=experiments/<exp_id>
make analyze-stability DATA_DIR=experiments/<exp_id>
make analyze-angle DATA_DIR=experiments/<exp_id>/angle
make analyze-all DATA_DIR=experiments/<exp_id>
```
