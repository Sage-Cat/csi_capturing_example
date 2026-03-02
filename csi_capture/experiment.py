from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from csi_capture.capture import (
    SerialPortAccessError,
    capture_stream,
    ensure_serial_port_access,
    serial_lines,
)


SUPPORTED_EXPERIMENT_TYPES = {"distance", "angle"}
SUPPORTED_OUTPUT_FORMATS = {"jsonl", "csv"}


class ExperimentConfigError(ValueError):
    """Raised when an experiment config is invalid."""


@dataclass(frozen=True)
class DeviceConfig:
    path: str
    baud: int
    timeout_s: float
    reconnect_on_error: bool
    reconnect_delay_s: float


@dataclass(frozen=True)
class CaptureConfig:
    output_format: str
    packets_per_repeat: Optional[int]
    duration_s: Optional[float]
    inter_trial_pause_s: float


@dataclass(frozen=True)
class TrialSpec:
    trial_id: str
    repeat_index: int
    ground_truth: dict[str, Any]


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_type: str
    exp_id: str
    run_ids: list[str]
    output_root: Path
    scenario_tags: list[str]
    environment: dict[str, str]
    device: DeviceConfig
    capture: CaptureConfig
    trials: list[TrialSpec]
    angle_array_config: Optional[dict[str, Any]]
    angle_geometry: Optional[dict[str, Any]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for idx, item in enumerate(value):
            if not isinstance(item, str):
                raise ExperimentConfigError(f"{field_name}[{idx}] must be a string.")
            text = item.strip()
            if not text:
                continue
            out.append(text)
        return out
    raise ExperimentConfigError(f"{field_name} must be a string or list of strings.")


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentConfigError(f"{field_name} must be an object.")
    return value


def _require_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ExperimentConfigError(f"{field_name} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentConfigError(f"{field_name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ExperimentConfigError(f"{field_name} must be > 0.")
    return parsed


def _require_positive_float(value: Any, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentConfigError(f"{field_name} must be a positive number.") from exc
    if parsed <= 0.0:
        raise ExperimentConfigError(f"{field_name} must be > 0.")
    return parsed


def _require_non_negative_float(value: Any, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentConfigError(f"{field_name} must be a non-negative number.") from exc
    if parsed < 0.0:
        raise ExperimentConfigError(f"{field_name} must be >= 0.")
    return parsed


def _require_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentConfigError(f"{field_name} must be numeric.") from exc


def _sanitize_token(value: float) -> str:
    text = f"{value:g}"
    text = text.replace("-", "neg").replace(".", "p")
    return text


def _normalize_run_ids(run_id: str, run_ids_raw: Any) -> list[str]:
    if run_ids_raw is None:
        return [run_id]
    if not isinstance(run_ids_raw, list):
        raise ExperimentConfigError("run_ids must be a non-empty list of strings.")

    normalized: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(run_ids_raw):
        if not isinstance(item, str):
            raise ExperimentConfigError(f"run_ids[{idx}] must be a string.")
        token = item.strip()
        if not token:
            raise ExperimentConfigError(f"run_ids[{idx}] cannot be empty.")
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)

    if not normalized:
        raise ExperimentConfigError("run_ids must contain at least one non-empty id.")
    return normalized


def _build_distance_trials(distance_cfg: dict[str, Any]) -> list[TrialSpec]:
    distances = distance_cfg.get("distances_m")
    if not isinstance(distances, list) or not distances:
        raise ExperimentConfigError("distance.distances_m must be a non-empty list.")
    repeats = _require_positive_int(
        distance_cfg.get("repeats_per_distance", 1), "distance.repeats_per_distance"
    )

    trials: list[TrialSpec] = []
    for distance in distances:
        distance_m = _require_positive_float(distance, "distance.distances_m[]")
        for rep in range(1, repeats + 1):
            trial_id = f"distance_{_sanitize_token(distance_m)}m_rep_{rep:03d}"
            trials.append(
                TrialSpec(
                    trial_id=trial_id,
                    repeat_index=rep,
                    ground_truth={"distance_m": distance_m},
                )
            )
    return trials


def _build_angle_trials(angle_cfg: dict[str, Any]) -> tuple[list[TrialSpec], dict[str, Any], dict[str, Any]]:
    angles = angle_cfg.get("angles")
    if not isinstance(angles, list) or not angles:
        raise ExperimentConfigError("angle.angles must be a non-empty list.")
    repeats = _require_positive_int(angle_cfg.get("repeats_per_angle"), "angle.repeats_per_angle")

    array_cfg = _require_dict(angle_cfg.get("array_config"), "angle.array_config")
    num_antennas = _require_positive_int(array_cfg.get("num_antennas"), "angle.array_config.num_antennas")
    antenna_spacing = array_cfg.get("antenna_spacing_m")
    if antenna_spacing is not None:
        antenna_spacing = _require_positive_float(
            antenna_spacing, "angle.array_config.antenna_spacing_m"
        )
    normalized_array_cfg = {
        "num_antennas": num_antennas,
        "antenna_spacing_m": antenna_spacing,
    }

    geometry_cfg = _require_dict(angle_cfg.get("geometry"), "angle.geometry")
    orientation_reference = geometry_cfg.get("orientation_reference")
    if not isinstance(orientation_reference, str) or not orientation_reference.strip():
        raise ExperimentConfigError("angle.geometry.orientation_reference must be a non-empty string.")
    measurement_positions = geometry_cfg.get("measurement_positions")
    if not isinstance(measurement_positions, str) or not measurement_positions.strip():
        raise ExperimentConfigError("angle.geometry.measurement_positions must be a non-empty string.")
    normalized_geometry_cfg = {
        "orientation_reference": orientation_reference.strip(),
        "measurement_positions": measurement_positions.strip(),
    }

    trials: list[TrialSpec] = []
    for angle in angles:
        angle_deg = _require_float(angle, "angle.angles[]")
        for rep in range(1, repeats + 1):
            trial_id = f"angle_{_sanitize_token(angle_deg)}deg_rep_{rep:03d}"
            trials.append(
                TrialSpec(
                    trial_id=trial_id,
                    repeat_index=rep,
                    ground_truth={"angle_deg": angle_deg},
                )
            )

    return trials, normalized_array_cfg, normalized_geometry_cfg


def _normalize_config(raw: dict[str, Any]) -> ExperimentConfig:
    experiment_type = str(raw.get("experiment_type", "")).strip().lower()
    if experiment_type not in SUPPORTED_EXPERIMENT_TYPES:
        raise ExperimentConfigError(
            f"experiment_type must be one of {sorted(SUPPORTED_EXPERIMENT_TYPES)}."
        )

    exp_id = str(raw.get("exp_id", "")).strip()
    if not exp_id:
        raise ExperimentConfigError("exp_id is required.")
    run_id = str(raw.get("run_id", _default_run_id())).strip()
    if not run_id:
        raise ExperimentConfigError("run_id cannot be empty.")
    run_ids = _normalize_run_ids(run_id=run_id, run_ids_raw=raw.get("run_ids"))

    output_root_raw = str(raw.get("output_root", "experiments")).strip()
    output_root = Path(output_root_raw) if output_root_raw else Path("experiments")

    scenario_tags = _normalize_string_list(raw.get("scenario_tags"), "scenario_tags")
    environment_raw = raw.get("environment", {})
    environment_cfg = _require_dict(environment_raw, "environment")
    room_id = str(environment_cfg.get("room_id", "")).strip()
    notes = str(environment_cfg.get("notes", "")).strip()
    environment = {"room_id": room_id, "notes": notes}

    device_raw = raw.get("device", {})
    device_cfg = _require_dict(device_raw, "device")
    device_path = str(device_cfg.get("path", "/dev/esp32_csi")).strip() or "/dev/esp32_csi"
    baud = _require_positive_int(device_cfg.get("baud", 921600), "device.baud")
    timeout_s = _require_positive_float(device_cfg.get("timeout_s", 1.0), "device.timeout_s")
    reconnect_on_error = bool(device_cfg.get("reconnect_on_error", False))
    reconnect_delay_s = _require_positive_float(
        device_cfg.get("reconnect_delay_s", 1.0), "device.reconnect_delay_s"
    )

    capture_raw = raw.get("capture", {})
    capture_cfg = _require_dict(capture_raw, "capture")
    output_format = str(capture_cfg.get("output_format", "jsonl")).strip().lower()
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ExperimentConfigError(
            f"capture.output_format must be one of {sorted(SUPPORTED_OUTPUT_FORMATS)}."
        )
    packets_per_repeat = capture_cfg.get("packets_per_repeat")
    duration_s = capture_cfg.get("duration_s")
    if packets_per_repeat is None and duration_s is None:
        raise ExperimentConfigError(
            "capture requires packets_per_repeat or duration_s (one is required)."
        )
    if packets_per_repeat is not None:
        packets_per_repeat = _require_positive_int(
            packets_per_repeat, "capture.packets_per_repeat"
        )
    if duration_s is not None:
        duration_s = _require_positive_float(duration_s, "capture.duration_s")
    if packets_per_repeat is not None and duration_s is not None:
        raise ExperimentConfigError(
            "capture.packets_per_repeat and capture.duration_s are mutually exclusive."
        )
    inter_trial_pause_s = _require_non_negative_float(
        capture_cfg.get("inter_trial_pause_s", 0.0), "capture.inter_trial_pause_s"
    )

    angle_array_config: Optional[dict[str, Any]] = None
    angle_geometry: Optional[dict[str, Any]] = None
    if experiment_type == "distance":
        distance_raw = raw.get("distance")
        distance_cfg = _require_dict(distance_raw, "distance")
        trials = _build_distance_trials(distance_cfg)
    else:
        angle_raw = raw.get("angle")
        angle_cfg = _require_dict(angle_raw, "angle")
        trials, angle_array_config, angle_geometry = _build_angle_trials(angle_cfg)

    return ExperimentConfig(
        experiment_type=experiment_type,
        exp_id=exp_id,
        run_ids=run_ids,
        output_root=output_root,
        scenario_tags=scenario_tags,
        environment=environment,
        device=DeviceConfig(
            path=device_path,
            baud=baud,
            timeout_s=timeout_s,
            reconnect_on_error=reconnect_on_error,
            reconnect_delay_s=reconnect_delay_s,
        ),
        capture=CaptureConfig(
            output_format=output_format,
            packets_per_repeat=packets_per_repeat,
            duration_s=duration_s,
            inter_trial_pause_s=inter_trial_pause_s,
        ),
        trials=trials,
        angle_array_config=angle_array_config,
        angle_geometry=angle_geometry,
    )


def load_experiment_config(config_path: Path) -> tuple[dict[str, Any], ExperimentConfig]:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ExperimentConfigError(f"Config JSON parse error: {exc}") from exc
    if not isinstance(raw, dict):
        raise ExperimentConfigError("Top-level config must be a JSON object.")
    normalized = _normalize_config(raw)
    return raw, normalized


def _git_info(repo_root: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> tuple[int, str]:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc.returncode, proc.stdout.strip()

    commit_code, commit_out = run_git(["rev-parse", "HEAD"])
    dirty_code, dirty_out = run_git(["status", "--porcelain"])
    commit = commit_out if commit_code == 0 and commit_out else "unknown"
    dirty = bool(dirty_out) if dirty_code == 0 else None
    return {"git_commit": commit, "git_dirty": dirty}


def _duration_limited_lines(lines: Iterable[str], duration_s: float) -> Iterator[str]:
    deadline = time.monotonic() + duration_s
    for line in lines:
        if time.monotonic() >= deadline:
            break
        yield line


def _config_to_dict(config: ExperimentConfig) -> dict[str, Any]:
    output: dict[str, Any] = {
        "experiment_type": config.experiment_type,
        "exp_id": config.exp_id,
        "run_ids": config.run_ids,
        "output_root": str(config.output_root),
        "scenario_tags": config.scenario_tags,
        "environment": config.environment,
        "device": {
            "path": config.device.path,
            "baud": config.device.baud,
            "timeout_s": config.device.timeout_s,
            "reconnect_on_error": config.device.reconnect_on_error,
            "reconnect_delay_s": config.device.reconnect_delay_s,
        },
        "capture": {
            "output_format": config.capture.output_format,
            "packets_per_repeat": config.capture.packets_per_repeat,
            "duration_s": config.capture.duration_s,
            "inter_trial_pause_s": config.capture.inter_trial_pause_s,
        },
    }
    if len(config.run_ids) == 1:
        output["run_id"] = config.run_ids[0]
    if config.experiment_type == "distance":
        distances = [trial.ground_truth["distance_m"] for trial in config.trials]
        output["distance"] = {
            "distances_m": sorted(set(distances), key=lambda v: (float(v), str(v))),
            "repeats_per_distance": max(
                trial.repeat_index for trial in config.trials if "distance_m" in trial.ground_truth
            ),
        }
    else:
        angles = [trial.ground_truth["angle_deg"] for trial in config.trials]
        output["angle"] = {
            "angles": sorted(set(angles), key=lambda v: (float(v), str(v))),
            "repeats_per_angle": max(
                trial.repeat_index for trial in config.trials if "angle_deg" in trial.ground_truth
            ),
            "array_config": config.angle_array_config,
            "geometry": config.angle_geometry,
        }
    return output


def _trial_metadata(config: ExperimentConfig, trial: TrialSpec, run_id: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "exp_id": config.exp_id,
        "experiment_type": config.experiment_type,
        "run_id": run_id,
        "trial_id": trial.trial_id,
        "repeat_index": trial.repeat_index,
        "scenario_tags": config.scenario_tags,
        "device_path": config.device.path,
        "room_id": config.environment.get("room_id", ""),
        "environment_notes": config.environment.get("notes", ""),
    }
    if config.scenario_tags:
        metadata["scenario"] = config.scenario_tags[0]
    metadata.update(trial.ground_truth)
    if config.experiment_type == "angle" and config.angle_array_config is not None:
        metadata["array_config"] = config.angle_array_config
    return metadata


def _manifest_template(
    config: ExperimentConfig,
    run_id: str,
    config_snapshot: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    git_meta = _git_info(repo_root)
    return {
        "exp_id": config.exp_id,
        "experiment_type": config.experiment_type,
        "run_id": run_id,
        "created_at_utc": _utc_now_iso(),
        "status": "running",
        "device": {
            "path": config.device.path,
            "baud": config.device.baud,
            "timeout_s": config.device.timeout_s,
            "reconnect_on_error": config.device.reconnect_on_error,
            "reconnect_delay_s": config.device.reconnect_delay_s,
        },
        "scenario_tags": config.scenario_tags,
        "environment": config.environment,
        "capture": {
            "output_format": config.capture.output_format,
            "packets_per_repeat": config.capture.packets_per_repeat,
            "duration_s": config.capture.duration_s,
            "inter_trial_pause_s": config.capture.inter_trial_pause_s,
        },
        "angle": {
            "array_config": config.angle_array_config,
            "geometry": config.angle_geometry,
        }
        if config.experiment_type == "angle"
        else None,
        "analysis_status": "not_run",
        "analysis_notes": "",
        **git_meta,
        "config_snapshot": config_snapshot,
        "resolved_config": _config_to_dict(config),
        "trials": [],
    }


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def run_config(config_path: Path, expected_type: Optional[str] = None) -> int:
    raw_config, config = load_experiment_config(config_path)
    if expected_type is not None and config.experiment_type != expected_type:
        raise ExperimentConfigError(
            f"Config experiment_type is '{config.experiment_type}', expected '{expected_type}'."
        )

    ensure_serial_port_access(config.device.path)

    repo_root = Path(__file__).resolve().parent.parent

    stream = serial_lines(
        port=config.device.path,
        baud=config.device.baud,
        timeout=config.device.timeout_s,
        reconnect_on_error=config.device.reconnect_on_error,
        reconnect_delay_s=config.device.reconnect_delay_s,
        yield_on_timeout=config.capture.duration_s is not None,
    )
    total_records = 0
    run_summaries: list[dict[str, Any]] = []
    active_manifest: Optional[dict[str, Any]] = None
    active_manifest_path: Optional[Path] = None

    try:
        run_count = len(config.run_ids)
        for run_index, run_id in enumerate(config.run_ids, start=1):
            run_dir = config.output_root / config.exp_id / config.experiment_type / f"run_{run_id}"
            run_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = run_dir / "manifest.json"
            manifest = _manifest_template(
                config=config,
                run_id=run_id,
                config_snapshot=raw_config,
                repo_root=repo_root,
            )
            manifest["run_index"] = run_index
            manifest["run_count"] = run_count

            trial_entries: list[dict[str, Any]] = []
            for trial in config.trials:
                trial_dir = run_dir / f"trial_{trial.trial_id}"
                extension = "jsonl" if config.capture.output_format == "jsonl" else "csv"
                out_file = trial_dir / f"capture.{extension}"
                entry = {
                    "trial_id": trial.trial_id,
                    "repeat_index": trial.repeat_index,
                    **trial.ground_truth,
                    "output_file": str(out_file),
                    "status": "pending",
                    "records_captured": 0,
                }
                trial_entries.append(entry)
            manifest["trials"] = trial_entries
            _write_manifest(manifest_path, manifest)
            active_manifest = manifest
            active_manifest_path = manifest_path

            print(
                f"Starting {config.experiment_type} experiment: exp_id={config.exp_id}, "
                f"run_id={run_id} ({run_index}/{run_count}), trials={len(config.trials)}, "
                f"device={config.device.path}"
            )

            run_total_records = 0
            for idx, trial in enumerate(config.trials):
                trial_dir = run_dir / f"trial_{trial.trial_id}"
                trial_dir.mkdir(parents=True, exist_ok=True)
                extension = "jsonl" if config.capture.output_format == "jsonl" else "csv"
                out_file = trial_dir / f"capture.{extension}"
                trial_entry = manifest["trials"][idx]
                trial_entry["status"] = "running"
                trial_entry["started_at_utc"] = _utc_now_iso()
                _write_manifest(manifest_path, manifest)

                metadata = _trial_metadata(config=config, trial=trial, run_id=run_id)
                with out_file.open("w", encoding="utf-8", newline="") as out_handle:
                    if config.capture.packets_per_repeat is not None:
                        written = capture_stream(
                            lines=stream,
                            out=out_handle,
                            output_format=config.capture.output_format,
                            max_records=config.capture.packets_per_repeat,
                            metadata=metadata,
                        )
                    else:
                        assert config.capture.duration_s is not None
                        written = capture_stream(
                            lines=_duration_limited_lines(stream, config.capture.duration_s),
                            out=out_handle,
                            output_format=config.capture.output_format,
                            max_records=None,
                            metadata=metadata,
                        )

                trial_entry["status"] = "completed"
                trial_entry["records_captured"] = written
                trial_entry["ended_at_utc"] = _utc_now_iso()
                run_total_records += written
                total_records += written
                _write_manifest(manifest_path, manifest)
                print(
                    f"Completed run {run_id} trial {idx + 1}/{len(config.trials)}: "
                    f"{trial.trial_id} -> {written} records"
                )
                if idx < len(config.trials) - 1 and config.capture.inter_trial_pause_s > 0.0:
                    pause_s = config.capture.inter_trial_pause_s
                    print(
                        f"Pause {pause_s:.1f}s before next trial. "
                        "Move receiver to the next angle mark now."
                    )
                    time.sleep(pause_s)

            manifest["status"] = "completed"
            manifest["ended_at_utc"] = _utc_now_iso()
            manifest["total_records"] = run_total_records
            _write_manifest(manifest_path, manifest)
            print(f"Run complete: run_id={run_id}, records={run_total_records}")
            print(f"Manifest: {manifest_path}")

            run_summaries.append(
                {"run_id": run_id, "records": run_total_records, "manifest_path": str(manifest_path)}
            )
            active_manifest = None
            active_manifest_path = None
    except KeyboardInterrupt:
        if active_manifest is not None and active_manifest_path is not None:
            active_manifest["status"] = "interrupted"
            active_manifest["ended_at_utc"] = _utc_now_iso()
            _write_manifest(active_manifest_path, active_manifest)
        raise

    print(
        f"Experiment complete. exp_id={config.exp_id}, runs={len(config.run_ids)}, "
        f"total_records={total_records}"
    )
    for summary in run_summaries:
        print(
            f"  run_id={summary['run_id']} records={summary['records']} "
            f"manifest={summary['manifest_path']}"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run config-driven CSI experiments (distance or angle)."
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run an experiment from a JSON config.")
    run_parser.add_argument("--config", required=True, help="Path to experiment config JSON.")

    distance_parser = sub.add_parser("distance", help="Run distance experiment config.")
    distance_parser.add_argument("--config", required=True, help="Path to experiment config JSON.")

    angle_parser = sub.add_parser("angle", help="Run angle experiment config.")
    angle_parser.add_argument("--config", required=True, help="Path to experiment config JSON.")

    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 2

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file does not exist: {config_path}")
        return 2

    try:
        if args.command == "run":
            return run_config(config_path)
        if args.command == "distance":
            return run_config(config_path, expected_type="distance")
        if args.command == "angle":
            return run_config(config_path, expected_type="angle")
        print(f"Error: unknown command {args.command}")
        return 2
    except ExperimentConfigError as err:
        print(f"Error: invalid config: {err}")
        return 2
    except SerialPortAccessError as err:
        print(f"Error: {err}")
        return 2
    except RuntimeError as err:
        print(f"Error: {err}")
        return 2
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
