PYTHON ?= python3
PORT ?= /dev/ttyACM1
BAUD ?= 921600
EXP_ID ?= smoke_$(shell date +%Y%m%d_%H%M%S)
SCENARIO ?= LoS
RUN_ID ?= 1
DISTANCE_M ?= 1.0
MAX_RECORDS ?= 20
DATA_DIR ?= experiments
OUT_DIR ?= out

.PHONY: test setup-vscode capture tx-node rx-smoke analyze-distance analyze-stability analyze-all

setup-vscode:
	./scripts/setup_vscode.sh

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

capture:
	$(PYTHON) -m csi_capture.capture -p $(PORT) -b $(BAUD) -o experiments/manual/csi_capture.jsonl --format jsonl

tx-node:
	./scripts/run_tx_laptop.sh --port $(PORT)

rx-smoke:
	./scripts/run_rx_laptop.sh --port $(PORT) --exp-id $(EXP_ID) --scenario $(SCENARIO) --run-id $(RUN_ID) --distance-m $(DISTANCE_M) --max-records $(MAX_RECORDS) --skip-build --skip-flash

analyze-distance:
	$(PYTHON) tools/analyze_wifi_distance_measurement.py --data_dir $(DATA_DIR) --out_dir $(OUT_DIR)/distance_measurement --seed 42

analyze-stability:
	$(PYTHON) tools/analyze_wifi_stability_statistics.py --data_dir $(DATA_DIR) --out_dir $(OUT_DIR)/stability_statistics --seed 42

analyze-all: analyze-distance analyze-stability
