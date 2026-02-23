PYTHON ?= python3

.PHONY: test capture

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

capture:
	$(PYTHON) -m csi_capture.capture -p /dev/ttyACM1 -b 921600 -o data/csi_capture.jsonl --format jsonl

