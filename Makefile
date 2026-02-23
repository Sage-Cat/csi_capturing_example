PYTHON ?= python3

.PHONY: test capture tx-node rx-smoke

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

capture:
	$(PYTHON) -m csi_capture.capture -p /dev/ttyACM1 -b 921600 -o data/csi_capture.jsonl --format jsonl

tx-node:
	./scripts/run_tx_laptop.sh --port /dev/ttyACM0

rx-smoke:
	./scripts/run_rx_laptop.sh --port /dev/ttyACM1 --scenario LoS --run-id 1 --distance-m 1.0 --max-records 20
