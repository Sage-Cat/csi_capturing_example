#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PORT="/dev/ttyACM0"
BAUD="921600"
TARGET="esp32s3"
FORMAT="jsonl"
MAX_RECORDS="2500"

BUILD=1
FLASH=1

EXP_ID="$(date +%Y%m%d_%H%M%S)"
SCENARIO="LoS"
RUN_ID="1"
DISTANCE_M="1.0"

CHANNEL="11"
BANDWIDTH_MHZ="20"
PACKET_RATE_HZ="250"
TX_POWER_DBM="default"

IDF_PATH_DEFAULT="$HOME/esp/esp-idf"
ESP_CSI_PATH_DEFAULT="$HOME/esp/esp-csi"
IDF_PATH="${IDF_PATH:-$IDF_PATH_DEFAULT}"
ESP_CSI_PATH="${ESP_CSI_PATH:-$ESP_CSI_PATH_DEFAULT}"

OUT_FILE=""

usage() {
  cat <<'EOF'
RX laptop runner (ESP32 csi_recv + structured CSI capture).

Usage:
  scripts/run_rx_laptop.sh [options]

Key experiment options:
  --exp-id <id>            Experiment id (default: current timestamp)
  --scenario <name>        LoS/NLoS_furniture/NLoS_human/NLoS_wall (default: LoS)
  --run-id <n>             Run index (default: 1)
  --distance-m <meters>    Ground-truth distance (default: 1.0)
  --max-records <n>        Number of CSI records to capture (default: 2500)

Device/build options:
  --port <path>            Serial port (default: /dev/ttyACM0)
  --baud <num>             Serial baud (default: 921600)
  --target <chip>          IDF target (default: esp32s3)
  --idf-path <path>        ESP-IDF path (default: $HOME/esp/esp-idf)
  --esp-csi-path <path>    esp-csi path (default: $HOME/esp/esp-csi)
  --skip-build             Do not run idf.py build
  --skip-flash             Do not run idf.py flash

Output/options:
  --format <jsonl|csv>     Output format (default: jsonl)
  --out <path>             Output file override

Meta options (written to meta.json):
  --channel <num>          Wi-Fi channel (default: 11)
  --bandwidth-mhz <num>    Bandwidth MHz (default: 20)
  --packet-rate-hz <num>   Packet rate (default: 250)
  --tx-power-dbm <value>   TX power note (default: default)

  -h, --help               Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --exp-id) EXP_ID="$2"; shift 2 ;;
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --distance-m) DISTANCE_M="$2"; shift 2 ;;
    --max-records) MAX_RECORDS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --baud) BAUD="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --idf-path) IDF_PATH="$2"; shift 2 ;;
    --esp-csi-path) ESP_CSI_PATH="$2"; shift 2 ;;
    --skip-build) BUILD=0; shift ;;
    --skip-flash) FLASH=0; shift ;;
    --format) FORMAT="$2"; shift 2 ;;
    --out) OUT_FILE="$2"; shift 2 ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    --bandwidth-mhz) BANDWIDTH_MHZ="$2"; shift 2 ;;
    --packet-rate-hz) PACKET_RATE_HZ="$2"; shift 2 ;;
    --tx-power-dbm) TX_POWER_DBM="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$FORMAT" != "jsonl" && "$FORMAT" != "csv" ]]; then
  echo "Unsupported format: $FORMAT (use jsonl or csv)" >&2
  exit 2
fi

if [[ ! -f "$IDF_PATH/export.sh" ]]; then
  echo "ESP-IDF export script not found: $IDF_PATH/export.sh" >&2
  exit 2
fi

RECV_DIR="$ESP_CSI_PATH/examples/get-started/csi_recv"
if [[ ! -d "$RECV_DIR" ]]; then
  echo "csi_recv directory not found: $RECV_DIR" >&2
  exit 2
fi

DISTANCE_TAG="${DISTANCE_M//./p}"
BASE_DIR="$REPO_ROOT/data/experiments/$EXP_ID/$SCENARIO/run_${RUN_ID}"
mkdir -p "$BASE_DIR"

if [[ -z "$OUT_FILE" ]]; then
  OUT_FILE="$BASE_DIR/distance_${DISTANCE_TAG}m.$FORMAT"
fi

META_FILE="$REPO_ROOT/data/experiments/$EXP_ID/meta.json"
if [[ ! -f "$META_FILE" ]]; then
  cat > "$META_FILE" <<EOF
{
  "exp_id": "$EXP_ID",
  "created_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "channel": $CHANNEL,
  "bandwidth_mhz": $BANDWIDTH_MHZ,
  "packet_rate_hz": $PACKET_RATE_HZ,
  "tx_power_dbm": "$TX_POWER_DBM",
  "target": "$TARGET",
  "notes": "ESP32-S3 CSI experiment (2.4 GHz only)"
}
EOF
fi

# shellcheck source=/dev/null
source "$IDF_PATH/export.sh" >/dev/null
cd "$RECV_DIR"

if [[ "$BUILD" -eq 1 ]]; then
  idf.py set-target "$TARGET"
  idf.py build
fi

if [[ "$FLASH" -eq 1 ]]; then
  idf.py -p "$PORT" -b "$BAUD" flash
fi

cd "$REPO_ROOT"
python3 -m csi_capture.capture \
  -p "$PORT" \
  -b "$BAUD" \
  -o "$OUT_FILE" \
  --format "$FORMAT" \
  --max-records "$MAX_RECORDS" \
  --exp-id "$EXP_ID" \
  --scenario "$SCENARIO" \
  --run-id "$RUN_ID" \
  --distance-m "$DISTANCE_M"

if [[ "$FORMAT" == "jsonl" ]]; then
  RECORDS_CAPTURED="$(wc -l < "$OUT_FILE" | tr -d ' ')"
else
  RECORDS_CAPTURED="$(( $(wc -l < "$OUT_FILE") - 1 ))"
fi

if [[ "$RECORDS_CAPTURED" -le 0 ]]; then
  echo "Error: no records captured in $OUT_FILE" >&2
  exit 1
fi

echo "RX capture complete: $RECORDS_CAPTURED records"
echo "Output: $OUT_FILE"
echo "Meta:   $META_FILE"

