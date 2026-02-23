# ESP32 CSI Experiment Toolkit (2 Laptops, 2 Boards)

This repository is prepared for the experiment workflow:

- **Laptop A (TX node):** flash/run `csi_send` on one ESP32-S3
- **Laptop B (RX node):** flash/run `csi_recv`, capture structured CSI data

Important for this setup:

- ESP32-S3 is used on **2.4 GHz only**
- Use fixed channel (e.g. 1/6/11) in firmware

## 1) System Dependencies (both laptops)

```bash
sudo apt update
sudo apt install -y \
  git wget flex bison gperf python3 python3-pip python3-venv python3-serial \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
sudo usermod -a -G dialout $USER
```

Logout/login after adding `dialout`.

## 2) ESP-IDF + esp-csi (both laptops)

```bash
mkdir -p ~/esp
cd ~/esp
git clone -b v5.5.3 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3
```

Optional convenience alias:

```bash
echo "alias get_idf='. $HOME/esp/esp-idf/export.sh'" >> ~/.bashrc
source ~/.bashrc
```

Clone esp-csi:

```bash
cd ~/esp
git clone https://github.com/espressif/esp-csi.git
```

## 3) This repository (both laptops)

```bash
cd ~
git clone git@github.com:Sage-Cat/csi_capturing_example.git
cd csi_capturing_example
pip3 install -r requirements.txt
```

## 4) Two Commands for Two Laptops

### Laptop A (TX) command

Connect TX ESP board, then run:

```bash
cd ~/csi_capturing_example
./scripts/run_tx_laptop.sh --port /dev/ttyACM0
```

This builds/flashes `csi_send` and leaves the transmitter running.

### Laptop B (RX) command

Connect RX ESP board, then run:

```bash
cd ~/csi_capturing_example
./scripts/run_rx_laptop.sh \
  --port /dev/ttyACM0 \
  --exp-id exp_2026_02_23_lab \
  --scenario LoS \
  --run-id 1 \
  --distance-m 1.0 \
  --max-records 2500
```

This builds/flashes `csi_recv`, captures CSI records, and stores experiment outputs.

## 5) Output Data Structure

Records are stored as JSONL (or CSV if requested) with at least:

- `timestamp` (host Unix time in ms)
- `rssi`
- `csi` (I/Q integer array)
- `esp_timestamp`
- `mac`

Experiment tags (from CLI) are attached to each row:

- `exp_id`
- `scenario`
- `run_id`
- `distance_m`

Example row:

```json
{"timestamp":1700000000000,"rssi":-15,"csi":[1,-2,3,-4],"esp_timestamp":119050,"mac":"1a:00:00:00:00:00","exp_id":"exp_2026_02_23_lab","scenario":"LoS","run_id":1,"distance_m":1.0}
```

Experiment files:

- `data/experiments/<exp_id>/meta.json`
- `data/experiments/<exp_id>/<scenario>/run_<run_id>/distance_<X>m.jsonl`

## 6) Local Smoke Test (single laptop with 2 boards)

If both boards are connected to one laptop:

```bash
cd ~/csi_capturing_example
./scripts/run_tx_laptop.sh --port /dev/ttyACM0
./scripts/run_rx_laptop.sh --port /dev/ttyACM1 --scenario LoS --run-id 1 --distance-m 1.0 --max-records 20
```

## 7) Tests

```bash
make test
```
