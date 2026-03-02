from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from csi_capture.capture import capture_stream, serial_lines
from csi_capture.core.dataset import RunCapture, load_static_sign_runs
from csi_capture.core.evaluation import classification_metrics, per_run_summary
from csi_capture.core.features import extract_window_features
from csi_capture.core.models import create_classifier, load_model_artifact, save_model_artifact

STATIC_SIGN_EXPERIMENT = "static_sign_v1"
STATIC_SIGN_LABELS = ("baseline", "hands_up")


class StaticSignError(RuntimeError):
    """Raised for static_sign_v1 pipeline failures."""


@dataclass(frozen=True)
class CaptureSummary:
    run_dir: Path
    run_id: str
    label: str
    records_captured: int


@dataclass(frozen=True)
class TrainSummary:
    model_path: Path
    metrics_path: Path
    metrics: dict[str, Any]


@dataclass(frozen=True)
class EvalSummary:
    report_path: Path
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _duration_limited_lines(lines: Iterable[str], duration_s: float) -> Iterable[str]:
    deadline = time.monotonic() + duration_s
    for line in lines:
        if time.monotonic() >= deadline:
            break
        yield line


def _ensure_label(label: str) -> str:
    text = label.strip().lower()
    if text not in STATIC_SIGN_LABELS:
        raise StaticSignError(f"label must be one of {sorted(STATIC_SIGN_LABELS)}")
    return text


def _ensure_dataset_id(dataset_id: str | None) -> str:
    if dataset_id and dataset_id.strip():
        return dataset_id.strip()
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def dry_run_capture(
    *,
    device_path: str,
    baud: int,
    packets: int,
    timeout_s: float,
    max_wait_s: float,
) -> int:
    if packets <= 0:
        raise StaticSignError("dry-run packets must be > 0")
    if max_wait_s <= 0:
        raise StaticSignError("dry-run max_wait_s must be > 0")

    lines = serial_lines(
        port=device_path,
        baud=baud,
        timeout=timeout_s,
        reconnect_on_error=False,
        reconnect_delay_s=1.0,
        yield_on_timeout=True,
    )
    sink = io.StringIO()
    written = capture_stream(
        _duration_limited_lines(lines, max_wait_s),
        out=sink,
        output_format="jsonl",
        max_records=packets,
        metadata=None,
    )
    if written < packets:
        raise StaticSignError(
            f"dry-run timed out after {max_wait_s}s; expected {packets} packets, got {written}"
        )
    return written


def capture_static_sign_runs(
    *,
    dataset_root: Path,
    dataset_id: str | None,
    label: str,
    runs: int,
    duration_s: float | None,
    packets_per_run: int | None,
    device_path: str,
    device_realpath: str,
    baud: int,
    timeout_s: float,
    subject_id: str | None,
    environment_id: str | None,
    notes: str | None,
) -> list[CaptureSummary]:
    label_norm = _ensure_label(label)
    dataset_id_norm = _ensure_dataset_id(dataset_id)

    if runs <= 0:
        raise StaticSignError("runs must be > 0")
    if duration_s is None and packets_per_run is None:
        raise StaticSignError("Provide duration_s or packets_per_run")
    if duration_s is not None and duration_s <= 0:
        raise StaticSignError("duration_s must be > 0")
    if packets_per_run is not None and packets_per_run <= 0:
        raise StaticSignError("packets_per_run must be > 0")

    summaries: list[CaptureSummary] = []
    exp_root = dataset_root / STATIC_SIGN_EXPERIMENT / dataset_id_norm / label_norm
    exp_root.mkdir(parents=True, exist_ok=True)

    for run_idx in range(1, runs + 1):
        run_id = f"{_new_run_id()}_{run_idx:03d}"
        run_dir = exp_root / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=False)

        start_time = _utc_now_iso()
        frames_path = run_dir / "frames.jsonl"

        packet_metadata = {
            "experiment_name": STATIC_SIGN_EXPERIMENT,
            "label": label_norm,
            "run_id": run_id,
            "subject_id": subject_id,
            "environment_id": environment_id,
        }
        packet_metadata = {k: v for k, v in packet_metadata.items() if v is not None}

        lines = serial_lines(
            port=device_path,
            baud=baud,
            timeout=timeout_s,
            reconnect_on_error=False,
            reconnect_delay_s=1.0,
            yield_on_timeout=duration_s is not None,
        )

        with frames_path.open("w", encoding="utf-8") as handle:
            if duration_s is not None:
                written = capture_stream(
                    _duration_limited_lines(lines, duration_s),
                    out=handle,
                    output_format="jsonl",
                    max_records=None,
                    metadata=packet_metadata,
                )
            else:
                written = capture_stream(
                    lines,
                    out=handle,
                    output_format="jsonl",
                    max_records=packets_per_run,
                    metadata=packet_metadata,
                )

        end_time = _utc_now_iso()

        metadata = {
            "schema_version": 1,
            "experiment_name": STATIC_SIGN_EXPERIMENT,
            "label": label_norm,
            "run_id": run_id,
            "subject_id": subject_id,
            "environment_id": environment_id,
            "device": "esp32_c3",
            "serial_dev": device_path,
            "serial_realpath": device_realpath,
            "start_time": start_time,
            "end_time": end_time,
            "sampling_params": {
                "baud": baud,
                "timeout_s": timeout_s,
                "duration_s": duration_s,
                "packets_per_run": packets_per_run,
            },
            "notes": notes,
            "records_captured": written,
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        summaries.append(
            CaptureSummary(
                run_dir=run_dir,
                run_id=run_id,
                label=label_norm,
                records_captured=written,
            )
        )

    return summaries


def build_feature_table(
    runs: list[RunCapture],
    *,
    window_s: float,
    overlap: float,
) -> pd.DataFrame:
    if window_s <= 0:
        raise StaticSignError("window_s must be > 0")

    rows: list[dict[str, Any]] = []
    window_ms = int(round(window_s * 1000.0))
    for run in runs:
        run_id = str(run.metadata["run_id"])
        label = str(run.metadata["label"])
        run_features = extract_window_features(
            run.frames,
            run_id=run_id,
            label=label,
            window_ms=window_ms,
            overlap=overlap,
        )
        for feat in run_features:
            rows.append(
                {
                    "run_id": feat.run_id,
                    "label": feat.label,
                    "window_index": feat.window_index,
                    "window_start_ms": feat.window_start_ms,
                    "window_end_ms": feat.window_end_ms,
                    "frame_count": feat.frame_count,
                    "mean_amp": feat.mean_amp,
                    "var_amp": feat.var_amp,
                    "rms_amp": feat.rms_amp,
                    "entropy_amp": feat.entropy_amp,
                }
            )

    if not rows:
        raise StaticSignError("No feature rows extracted from dataset")

    frame = pd.DataFrame(rows)
    frame = frame.sort_values(["run_id", "window_index"]).reset_index(drop=True)
    return frame


def _group_split(
    frame: pd.DataFrame,
    *,
    test_size: float,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    groups = frame["run_id"].astype(str)
    unique_groups = groups.nunique()

    if unique_groups < 2:
        idx = np.arange(len(frame))
        return idx, idx

    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_seed)
    train_idx, test_idx = next(splitter.split(frame, groups=groups))
    return train_idx, test_idx


def _frame_to_xy(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = frame[["mean_amp", "var_amp", "rms_amp", "entropy_amp"]].to_numpy(dtype=np.float32)
    y = frame["label"].astype(str).to_numpy()
    run_ids = frame["run_id"].astype(str).to_numpy()
    return x, y, run_ids


def train_static_sign_model(
    *,
    dataset_path: Path,
    model_name: str,
    window_s: float,
    overlap: float,
    test_size: float,
    random_seed: int,
    model_path: Path,
) -> TrainSummary:
    runs = load_static_sign_runs(dataset_path)
    frame = build_feature_table(runs, window_s=window_s, overlap=overlap)
    x, y, run_ids = _frame_to_xy(frame)

    train_idx, test_idx = _group_split(frame, test_size=test_size, random_seed=random_seed)
    clf = create_classifier(model_name)
    clf.fit(x[train_idx], y[train_idx])

    pred_test = clf.predict(x[test_idx])
    metrics = classification_metrics(y[test_idx], pred_test, labels=STATIC_SIGN_LABELS)
    metrics["split"] = {
        "train_windows": int(train_idx.size),
        "test_windows": int(test_idx.size),
        "train_runs": sorted(set(run_ids[train_idx].tolist())),
        "test_runs": sorted(set(run_ids[test_idx].tolist())),
    }
    metrics["per_run_summary"] = per_run_summary(run_ids[test_idx], y[test_idx], pred_test)

    model_metadata = {
        "experiment_name": STATIC_SIGN_EXPERIMENT,
        "labels": list(STATIC_SIGN_LABELS),
        "model_name": model_name,
        "window_s": window_s,
        "overlap": overlap,
        "feature_columns": ["mean_amp", "var_amp", "rms_amp", "entropy_amp"],
    }
    save_model_artifact(model_path, clf, model_metadata)

    metrics_path = model_path.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return TrainSummary(model_path=model_path, metrics_path=metrics_path, metrics=metrics)


def evaluate_static_sign_model(
    *,
    dataset_path: Path,
    model_path: Path,
    report_path: Path,
    window_s: float | None,
    overlap: float | None,
) -> EvalSummary:
    artifact = load_model_artifact(model_path)
    model = artifact["model"]
    metadata = artifact.get("metadata", {})

    window_s_eff = window_s if window_s is not None else float(metadata.get("window_s", 1.0))
    overlap_eff = overlap if overlap is not None else float(metadata.get("overlap", 0.5))

    runs = load_static_sign_runs(dataset_path)
    frame = build_feature_table(runs, window_s=window_s_eff, overlap=overlap_eff)
    x, y, run_ids = _frame_to_xy(frame)

    pred = model.predict(x)
    report = classification_metrics(y, pred, labels=STATIC_SIGN_LABELS)
    report["per_run_summary"] = per_run_summary(run_ids, y, pred)
    report["dataset_path"] = str(dataset_path)
    report["model_path"] = str(model_path)
    report["model_metadata"] = metadata
    report["window_s"] = window_s_eff
    report["overlap"] = overlap_eff

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EvalSummary(report_path=report_path, report=report)


def validate_static_sign_config(mode: str, config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise StaticSignError("config must be a JSON object")
    if config.get("experiment") != STATIC_SIGN_EXPERIMENT:
        raise StaticSignError(f"config.experiment must be '{STATIC_SIGN_EXPERIMENT}'")

    mode_norm = mode.strip().lower()
    if mode_norm == "capture":
        label = str(config.get("label", "")).strip().lower()
        if label not in STATIC_SIGN_LABELS:
            raise StaticSignError("capture config label must be baseline or hands_up")
        runs = config.get("runs")
        if not isinstance(runs, int) or runs <= 0:
            raise StaticSignError("capture config runs must be integer > 0")
        duration_s = config.get("duration_s")
        packets_per_run = config.get("packets_per_run")
        if duration_s is None and packets_per_run is None:
            raise StaticSignError("capture config requires duration_s or packets_per_run")
    elif mode_norm == "train":
        model = str(config.get("model", "")).strip()
        dataset = str(config.get("dataset", "")).strip()
        if not model:
            raise StaticSignError("train config model is required")
        if not dataset:
            raise StaticSignError("train config dataset is required")
    elif mode_norm == "eval":
        dataset = str(config.get("dataset", "")).strip()
        model = str(config.get("model_artifact", "")).strip()
        if not dataset:
            raise StaticSignError("eval config dataset is required")
        if not model:
            raise StaticSignError("eval config model_artifact is required")
    else:
        raise StaticSignError("mode must be one of: capture, train, eval")
