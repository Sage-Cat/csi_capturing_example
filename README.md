# CSI Capture Utility

This tool avoids `idf.py monitor` and reads CSI directly from serial.

## Why this fixes the monitor issue

`idf.py monitor` can trap terminal key handling.  
This project uses `pyserial` directly, so stopping capture is just `Ctrl+C`.

## Output structure

Each captured CSI record is stored as:

- `timestamp` (host Unix time in ms)
- `rssi` (RSSI from `CSI_DATA`)
- `csi` (list of integer I/Q values)
- `esp_timestamp`
- `mac`

Example JSONL row:

```json
{"timestamp":1700000000000,"rssi":-15,"csi":[1,-2,3,-4],"esp_timestamp":119050,"mac":"1a:00:00:00:00:00"}
```

## Setup

```bash
pip3 install -r requirements.txt
```

## Capture

```bash
python3 -m csi_capture.capture -p /dev/ttyACM1 -b 921600 -o data/csi_capture.jsonl --format jsonl
```

Or:

```bash
make capture
```

## Tests

```bash
make test
```

