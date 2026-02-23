# ESP32 CSI/RSSI Experiment Toolkit

Toolkit for capturing ESP32 CSI packets, organizing experiment runs, and producing RSSI/CSI analysis reports.

Primary workflow:

- Laptop A (TX): flash/run `csi_send`
- Laptop B (RX): flash/run `csi_recv`, capture CSI stream, attach experiment metadata

## Repository Layout

```text
csi_capture/              # Python capture/parser modules
scripts/                  # Operational scripts (TX/RX, local setup)
tools/                    # Analysis scripts
tests/                    # Unit tests
docs/                     # Analysis notes and methodology docs
experiments/              # Local raw runs (git-ignored except README/.gitkeep)
out/                      # Local generated figures/tables/reports (git-ignored except README/.gitkeep)
data/                     # Small reusable sample data only
.vscode.template/         # Tracked VS Code defaults copied to local .vscode/
```

`experiments/`, `out/`, build files, and `.vscode/` are intentionally ignored so students can run scripts locally without polluting git history.

## 1) System Dependencies (Both Laptops)

```bash
sudo apt update
sudo apt install -y \
  git wget flex bison gperf python3 python3-pip python3-venv python3-serial \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
sudo usermod -a -G dialout $USER
```

Log out and log in again after adding `dialout`.

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
./scripts/run_tx_laptop.sh --port /dev/ttyACM0
```

RX node:

```bash
./scripts/run_rx_laptop.sh \
  --port /dev/ttyACM1 \
  --exp-id exp_2026_02_23_lab \
  --scenario LoS \
  --run-id 1 \
  --distance-m 1.0 \
  --max-records 2500
```

By default, RX output is stored under `experiments/<exp_id>/...`.

## 5) Experiment Data Structure

Each captured row stores:

- `timestamp` (host Unix ms)
- `rssi`
- `csi` (I/Q integer array)
- `esp_timestamp`
- `mac`
- plus metadata tags (`exp_id`, `scenario`, `run_id`, `distance_m`)

Example:

```json
{"timestamp":1700000000000,"rssi":-15,"csi":[1,-2,3,-4],"esp_timestamp":119050,"mac":"1a:00:00:00:00:00","exp_id":"exp_2026_02_23_lab","scenario":"LoS","run_id":1,"distance_m":1.0}
```

Layout:

- `experiments/<exp_id>/meta.json`
- `experiments/<exp_id>/<scenario>/run_<run_id>/distance_<X>m.jsonl`

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

Outputs are written to `out/` and are git-ignored.

## 7) Make Targets

```bash
make setup-vscode
make test
make tx-node PORT=/dev/ttyACM0
make rx-smoke PORT=/dev/ttyACM1 EXP_ID=exp_smoke
make analyze-distance DATA_DIR=experiments/<exp_id>
make analyze-stability DATA_DIR=experiments/<exp_id>
make analyze-all DATA_DIR=experiments/<exp_id>
```
