from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import IO, Iterable, Optional, TextIO

from csi_capture.parser import CSIRecord, parse_csi_line


def _record_to_dict(record: CSIRecord) -> dict:
    return {
        "timestamp": record.timestamp,
        "rssi": record.rssi,
        "csi": record.csi,
        "esp_timestamp": record.esp_timestamp,
        "mac": record.mac,
    }


def _write_jsonl(f: TextIO, record: CSIRecord) -> None:
    f.write(json.dumps(_record_to_dict(record), separators=(",", ":")) + "\n")


def _write_csv(writer: csv.DictWriter, record: CSIRecord) -> None:
    writer.writerow(
        {
            "timestamp": record.timestamp,
            "rssi": record.rssi,
            "csi": json.dumps(record.csi, separators=(",", ":")),
            "esp_timestamp": record.esp_timestamp,
            "mac": record.mac,
        }
    )


def capture_stream(
    lines: Iterable[str],
    out: IO[str],
    output_format: str = "jsonl",
    max_records: Optional[int] = None,
) -> int:
    csv_writer = None
    if output_format == "csv":
        csv_writer = csv.DictWriter(
            out, fieldnames=["timestamp", "rssi", "csi", "esp_timestamp", "mac"]
        )
        csv_writer.writeheader()

    written = 0
    for line in lines:
        ts = int(time.time() * 1000)
        record = parse_csi_line(line, timestamp=ts)
        if record is None:
            continue

        if output_format == "jsonl":
            _write_jsonl(out, record)
        else:
            _write_csv(csv_writer, record)

        written += 1
        if max_records and written >= max_records:
            break

    return written


def _serial_lines(port: str, baud: int):
    # Import here so parser tests run without serial dependency.
    try:
        import serial
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'pyserial' for this Python interpreter. "
            "Install with: python3 -m pip install pyserial "
            "or (for sudo/system python) sudo apt install python3-serial"
        ) from exc

    with serial.Serial(port=port, baudrate=baud, timeout=1) as ser:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            yield raw.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture ESP CSI_DATA into structured timestamp,rssi,csi records."
    )
    parser.add_argument("-p", "--port", required=True, help="Serial port, e.g. /dev/ttyACM1")
    parser.add_argument("-b", "--baud", type=int, default=921600, help="Serial baud rate")
    parser.add_argument(
        "-o",
        "--output",
        default="csi_capture.jsonl",
        help="Output file path (jsonl or csv)",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="Output format",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Stop after N parsed CSI records",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(args.port):
        print(f"Error: serial port does not exist: {args.port}")
        return 2
    if not os.access(args.port, os.R_OK | os.W_OK):
        print(f"Error: no read/write access to serial port: {args.port}")
        print("Fix:")
        print("  1) sudo usermod -a -G dialout $USER")
        print("  2) logout/login (or restart terminal session manager)")
        print("  3) verify: id -nG  (must include dialout)")
        return 2

    print(
        f"Capturing CSI from {args.port} @ {args.baud}. "
        f"Writing {args.format} to {output_path}. Press Ctrl+C to stop."
    )

    written = 0
    try:
        with output_path.open("w", encoding="utf-8", newline="") as out:
            written = capture_stream(
                _serial_lines(args.port, args.baud),
                out=out,
                output_format=args.format,
                max_records=args.max_records,
            )
    except KeyboardInterrupt:
        pass

    print(f"Done. Records captured: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
