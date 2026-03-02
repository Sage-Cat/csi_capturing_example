from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

STATIC_SIGN_SCHEMA_VERSION = 1
STATIC_SIGN_LABELS = ("baseline", "hands_up")


@dataclass(frozen=True)
class RunCapture:
    run_dir: Path
    metadata: dict[str, Any]
    frames: list[dict[str, Any]]


class DatasetValidationError(ValueError):
    """Raised when dataset schema/content checks fail."""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise DatasetValidationError(f"Expected JSON object: {path}")
    return payload


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _iter_csv(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield dict(row)


def iter_packet_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Adapter reader supporting legacy/new packet files."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        yield from _iter_jsonl(path)
        return
    if suffix == ".csv":
        yield from _iter_csv(path)
        return
    raise DatasetValidationError(f"Unsupported packet file extension: {path}")


def validate_run_metadata(
    metadata: dict[str, Any],
    *,
    expected_experiment: str = "static_sign_v1",
    allowed_labels: tuple[str, ...] = STATIC_SIGN_LABELS,
) -> None:
    required_str_fields = (
        "experiment_name",
        "label",
        "run_id",
        "device",
        "serial_dev",
        "start_time",
        "end_time",
    )
    for field in required_str_fields:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DatasetValidationError(f"metadata.{field} must be a non-empty string")

    if metadata.get("experiment_name") != expected_experiment:
        raise DatasetValidationError(
            f"metadata.experiment_name must be '{expected_experiment}'"
        )

    label = str(metadata.get("label", "")).strip().lower()
    if label not in allowed_labels:
        raise DatasetValidationError(
            f"metadata.label must be one of {sorted(allowed_labels)}"
        )

    schema_version = metadata.get("schema_version")
    if schema_version != STATIC_SIGN_SCHEMA_VERSION:
        raise DatasetValidationError(
            f"metadata.schema_version must be {STATIC_SIGN_SCHEMA_VERSION}"
        )

    sampling_params = metadata.get("sampling_params")
    if not isinstance(sampling_params, dict):
        raise DatasetValidationError("metadata.sampling_params must be an object")

    for optional in ("subject_id", "environment_id", "notes"):
        value = metadata.get(optional)
        if value is not None and not isinstance(value, str):
            raise DatasetValidationError(f"metadata.{optional} must be string or null")


def load_static_sign_runs(dataset_root: Path) -> list[RunCapture]:
    if not dataset_root.exists():
        raise DatasetValidationError(f"Dataset root does not exist: {dataset_root}")

    runs: list[RunCapture] = []
    meta_paths = sorted(dataset_root.rglob("metadata.json"))
    if not meta_paths:
        raise DatasetValidationError(
            f"No metadata.json files found under dataset root: {dataset_root}"
        )

    for meta_path in meta_paths:
        metadata = _read_json(meta_path)
        validate_run_metadata(metadata)
        run_dir = meta_path.parent
        frames_path = run_dir / "frames.jsonl"
        if not frames_path.exists():
            raise DatasetValidationError(f"Missing frames.jsonl for run: {run_dir}")

        frames = list(iter_packet_rows(frames_path))
        if not frames:
            raise DatasetValidationError(f"No frames found in {frames_path}")

        runs.append(RunCapture(run_dir=run_dir, metadata=metadata, frames=frames))

    return runs
