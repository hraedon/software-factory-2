.PHONY: lint format test cov audit check golden-run

PYTEST := .venv/bin/python -m pytest
VULTURE := .venv/bin/vulture

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

test:
	$(PYTEST) tests/ -q

cov:
	$(PYTEST) tests/ -q --cov=factory --cov-report=term-missing

audit:
	$(VULTURE) src/factory/ tests/ .vulture_whitelist.py --min-confidence 80

check: lint audit test

golden-run:
	@test -n "$(CONFIG)" || (echo "CONFIG=<path> required" && exit 1)
	python populate_work_items.py --config $(CONFIG) --reset
	python -m factory.runner --config $(CONFIG) &
	python -m factory.gate_process --config $(CONFIG) &
	python -m factory.scheduler --config $(CONFIG) &
	wait
	python -m factory.report --config $(CONFIG)
	python -m factory.telemetry --config $(CONFIG)
	python -m factory.telemetry --verify --config $(CONFIG)