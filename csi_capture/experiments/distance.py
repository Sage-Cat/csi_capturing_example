from __future__ import annotations

from pathlib import Path

from csi_capture.experiment import run_config


def run_distance_capture_config(config_path: Path) -> int:
    """Compatibility adapter for existing distance config-driven capture."""
    return run_config(config_path, expected_type="distance")
