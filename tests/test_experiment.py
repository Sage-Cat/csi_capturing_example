import json
import tempfile
import unittest
from pathlib import Path

from csi_capture.experiment import ExperimentConfigError, load_experiment_config


class ExperimentConfigTests(unittest.TestCase):
    def _load(self, payload: dict):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_experiment_config(path)

    def test_angle_config_builds_trials(self):
        payload = {
            "experiment_type": "angle",
            "exp_id": "exp_angle_test",
            "run_id": "1",
            "capture": {"packets_per_repeat": 10},
            "angle": {
                "angles": [0, 30, 60],
                "repeats_per_angle": 2,
                "array_config": {"num_antennas": 1, "antenna_spacing_m": None},
                "geometry": {
                    "orientation_reference": "0 deg points to AP",
                    "measurement_positions": "AP fixed, receiver rotated",
                },
            },
        }
        _raw, config = self._load(payload)
        self.assertEqual(config.experiment_type, "angle")
        self.assertEqual(config.device.path, "/dev/esp32_csi")
        self.assertEqual(len(config.trials), 6)
        self.assertIn("angle_deg", config.trials[0].ground_truth)
        self.assertEqual(config.angle_array_config["num_antennas"], 1)

    def test_distance_config_builds_trials(self):
        payload = {
            "experiment_type": "distance",
            "exp_id": "exp_distance_test",
            "run_id": "1",
            "capture": {"packets_per_repeat": 5},
            "distance": {"distances_m": [1.0, 2.0], "repeats_per_distance": 3},
            "scenario_tags": ["LoS"],
        }
        _raw, config = self._load(payload)
        self.assertEqual(config.experiment_type, "distance")
        self.assertEqual(len(config.trials), 6)
        self.assertEqual(config.trials[0].ground_truth["distance_m"], 1.0)
        self.assertEqual(config.scenario_tags, ["LoS"])

    def test_capture_budget_is_required(self):
        payload = {
            "experiment_type": "distance",
            "exp_id": "exp_distance_test",
            "run_id": "1",
            "capture": {},
            "distance": {"distances_m": [1.0], "repeats_per_distance": 1},
        }
        with self.assertRaises(ExperimentConfigError):
            self._load(payload)

    def test_packets_and_duration_are_mutually_exclusive(self):
        payload = {
            "experiment_type": "distance",
            "exp_id": "exp_distance_test",
            "run_id": "1",
            "capture": {"packets_per_repeat": 5, "duration_s": 1.0},
            "distance": {"distances_m": [1.0], "repeats_per_distance": 1},
        }
        with self.assertRaises(ExperimentConfigError):
            self._load(payload)

    def test_angle_geometry_required(self):
        payload = {
            "experiment_type": "angle",
            "exp_id": "exp_angle_test",
            "run_id": "1",
            "capture": {"packets_per_repeat": 5},
            "angle": {
                "angles": [0],
                "repeats_per_angle": 1,
                "array_config": {"num_antennas": 2, "antenna_spacing_m": 0.05},
                "geometry": {"orientation_reference": "front axis"},
            },
        }
        with self.assertRaises(ExperimentConfigError):
            self._load(payload)


if __name__ == "__main__":
    unittest.main()
