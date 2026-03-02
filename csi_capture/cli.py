from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from csi_capture.core.device import (
    DeviceAccessError,
    format_device_banner,
    list_serial_candidates,
    resolve_serial_device,
    validate_serial_device_access,
)
from csi_capture.experiments.distance import run_distance_capture_config
from csi_capture.experiments.static_sign_v1 import (
    STATIC_SIGN_EXPERIMENT,
    StaticSignError,
    capture_static_sign_runs,
    dry_run_capture,
    evaluate_static_sign_model,
    train_static_sign_model,
    validate_static_sign_config,
)
from csi_capture.experiment import ExperimentConfigError


def parse_duration_s(text: str) -> float:
    value = text.strip().lower()
    if not value:
        raise ValueError("duration value is empty")
    if value.endswith("ms"):
        return float(value[:-2]) / 1000.0
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("m"):
        return float(value[:-1]) * 60.0
    if value.endswith("h"):
        return float(value[:-1]) * 3600.0
    return float(value)


def _default_artifact_path(experiment: str, model: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("artifacts") / experiment / stamp / f"{model}.pkl"


def _print_list_devices() -> None:
    candidates = list_serial_candidates()
    if not candidates:
        print(
            "No candidate serial devices found under "
            "/dev/esp32_csi, /dev/ttyACM*, /dev/ttyUSB*, "
            "/dev/tty.usbmodem*, /dev/cu.usbmodem*, /dev/tty.usbserial*, /dev/cu.usbserial*."
        )
        return

    print("Serial device candidates:")
    for path in candidates:
        realpath = str(Path(path).resolve(strict=False))
        marker = ""
        if path != realpath:
            marker = f" -> {realpath}"
        print(f"- {path}{marker}")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    return payload


def cmd_capture(args: argparse.Namespace) -> int:
    if args.experiment != STATIC_SIGN_EXPERIMENT:
        print(f"Error: unsupported experiment '{args.experiment}' for capture")
        return 2

    try:
        device = resolve_serial_device(cli_device=args.device, env=os.environ)
        print(format_device_banner(device))
        validate_serial_device_access(device.path)

        if args.dry_run_packets and args.dry_run_packets > 0:
            max_wait_s = parse_duration_s(args.dry_run_timeout)
            written = dry_run_capture(
                device_path=device.path,
                baud=args.baud,
                packets=args.dry_run_packets,
                timeout_s=args.timeout_s,
                max_wait_s=max_wait_s,
            )
            print(f"Dry-run success. Parsed packets: {written}")
            return 0

        if not args.label:
            print("Error: --label is required unless --dry-run-packets is used")
            return 2

        if args.packets_per_run is not None:
            duration_s = None
        else:
            duration_s = parse_duration_s(args.duration) if args.duration else None
        summaries = capture_static_sign_runs(
            dataset_root=Path(args.dataset_root),
            dataset_id=args.dataset_id,
            label=args.label,
            runs=args.runs,
            duration_s=duration_s,
            packets_per_run=args.packets_per_run,
            device_path=device.path,
            device_realpath=device.realpath,
            baud=args.baud,
            timeout_s=args.timeout_s,
            subject_id=args.subject_id,
            environment_id=args.environment_id,
            notes=args.notes,
        )
    except (ValueError, DeviceAccessError, RuntimeError, StaticSignError) as err:
        print(f"Error: {err}")
        return 2

    total = sum(item.records_captured for item in summaries)
    print(f"Capture complete. runs={len(summaries)} total_records={total}")
    for item in summaries:
        print(f"- run_id={item.run_id} label={item.label} records={item.records_captured} dir={item.run_dir}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    if args.experiment != STATIC_SIGN_EXPERIMENT:
        print(f"Error: unsupported experiment '{args.experiment}' for train")
        return 2

    artifact = Path(args.artifact) if args.artifact else _default_artifact_path(args.experiment, args.model)
    try:
        window_s = parse_duration_s(args.window)
        summary = train_static_sign_model(
            dataset_path=Path(args.dataset),
            model_name=args.model,
            window_s=window_s,
            overlap=args.overlap,
            test_size=args.test_size,
            random_seed=args.seed,
            model_path=artifact,
        )
    except (ValueError, RuntimeError, StaticSignError) as err:
        print(f"Error: {err}")
        return 2

    print(f"Model artifact: {summary.model_path}")
    print(f"Metrics file: {summary.metrics_path}")
    print(
        "Train split metrics: "
        f"accuracy={summary.metrics['accuracy']:.4f} "
        f"precision={summary.metrics['precision']:.4f} "
        f"recall={summary.metrics['recall']:.4f} "
        f"f1={summary.metrics['f1']:.4f}"
    )
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    if args.experiment != STATIC_SIGN_EXPERIMENT:
        print(f"Error: unsupported experiment '{args.experiment}' for eval")
        return 2

    try:
        window_s = parse_duration_s(args.window) if args.window else None
        summary = evaluate_static_sign_model(
            dataset_path=Path(args.dataset),
            model_path=Path(args.model),
            report_path=Path(args.report),
            window_s=window_s,
            overlap=args.overlap,
        )
    except (ValueError, RuntimeError, StaticSignError) as err:
        print(f"Error: {err}")
        return 2

    report = summary.report
    print(f"Eval report: {summary.report_path}")
    print(
        "Metrics: "
        f"accuracy={report['accuracy']:.4f} "
        f"precision={report['precision']:.4f} "
        f"recall={report['recall']:.4f} "
        f"f1={report['f1']:.4f}"
    )
    print(f"Confusion matrix ({report['labels']}): {report['confusion_matrix']}")
    return 0


def cmd_validate_config(args: argparse.Namespace) -> int:
    if args.experiment != STATIC_SIGN_EXPERIMENT:
        print(f"Error: unsupported experiment '{args.experiment}' for validate-config")
        return 2

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config path does not exist: {config_path}")
        return 2

    try:
        payload = _load_json(config_path)
        validate_static_sign_config(args.mode, payload)
    except (ValueError, StaticSignError, json.JSONDecodeError) as err:
        print(f"Error: {err}")
        return 2

    print(f"Config validation passed: mode={args.mode} file={config_path}")
    return 0


def cmd_distance(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file does not exist: {config_path}")
        return 2
    try:
        return run_distance_capture_config(config_path)
    except (ExperimentConfigError, RuntimeError) as err:
        print(f"Error: {err}")
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified CSI experiment CLI (capture/train/eval).",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help=(
            "List serial candidates: /dev/esp32_csi, /dev/ttyACM*, /dev/ttyUSB*, "
            "/dev/tty.usbmodem*, /dev/cu.usbmodem*, /dev/tty.usbserial*, /dev/cu.usbserial*"
        ),
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-devices", help="List serial candidates.")

    capture = sub.add_parser("capture", help="Capture labeled dataset runs.")
    capture.add_argument("--experiment", required=True, help="Experiment name (static_sign_v1)")
    capture.add_argument("--label", default=None, help="Label (baseline or hands_up)")
    capture.add_argument("--runs", type=int, default=1, help="Number of runs to capture")
    capture.add_argument(
        "--duration",
        default="20s",
        help="Duration per run (e.g. 20s, 1m). Ignored when --packets-per-run is used.",
    )
    capture.add_argument("--packets-per-run", type=int, default=None, help="Capture N packets per run")
    capture.add_argument("--dataset-root", default="data/experiments", help="Dataset root directory")
    capture.add_argument("--dataset-id", default=None, help="Dataset id (default: UTC date YYYYMMDD)")
    capture.add_argument("--device", default=None, help="Serial device path override")
    capture.add_argument("--baud", type=int, default=921600, help="Serial baud")
    capture.add_argument("--timeout-s", type=float, default=1.0, help="Serial read timeout seconds")
    capture.add_argument("--subject-id", default=None, help="Optional subject identifier")
    capture.add_argument("--environment-id", default=None, help="Optional environment identifier")
    capture.add_argument("--notes", default=None, help="Optional notes")
    capture.add_argument(
        "--dry-run-packets",
        type=int,
        default=0,
        help="Open serial and parse N packets, then exit without writing dataset",
    )
    capture.add_argument(
        "--dry-run-timeout",
        default="10s",
        help="Maximum wait duration for dry-run packet sampling",
    )

    train = sub.add_parser("train", help="Train model for an experiment dataset.")
    train.add_argument("--experiment", required=True, help="Experiment name (static_sign_v1)")
    train.add_argument("--dataset", required=True, help="Dataset directory path")
    train.add_argument("--model", default="svm_linear", help="Model name: svm_linear or logreg")
    train.add_argument("--window", default="1s", help="Feature window duration")
    train.add_argument("--overlap", type=float, default=0.5, help="Window overlap [0,1)")
    train.add_argument("--test-size", type=float, default=0.3, help="Group split test fraction")
    train.add_argument("--seed", type=int, default=42, help="Random seed")
    train.add_argument("--artifact", default=None, help="Output model artifact path")

    eval_parser = sub.add_parser("eval", help="Evaluate a trained model.")
    eval_parser.add_argument("--experiment", required=True, help="Experiment name (static_sign_v1)")
    eval_parser.add_argument("--dataset", required=True, help="Dataset directory path")
    eval_parser.add_argument("--model", required=True, help="Model artifact path")
    eval_parser.add_argument("--report", required=True, help="Output report JSON path")
    eval_parser.add_argument("--window", default=None, help="Optional window override")
    eval_parser.add_argument("--overlap", type=float, default=None, help="Optional overlap override")

    validate = sub.add_parser("validate-config", help="Validate experiment config JSON")
    validate.add_argument("--experiment", required=True, help="Experiment name")
    validate.add_argument("--mode", required=True, choices=("capture", "train", "eval"))
    validate.add_argument("--config", required=True, help="Config JSON path")

    distance = sub.add_parser("distance", help="Compatibility adapter to distance capture config")
    distance.add_argument("--config", required=True, help="Distance config path")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_devices:
        _print_list_devices()
        return 0

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "list-devices":
        _print_list_devices()
        return 0
    if args.command == "capture":
        return cmd_capture(args)
    if args.command == "train":
        return cmd_train(args)
    if args.command == "eval":
        return cmd_eval(args)
    if args.command == "validate-config":
        return cmd_validate_config(args)
    if args.command == "distance":
        return cmd_distance(args)

    print(f"Error: unknown command '{args.command}'")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
