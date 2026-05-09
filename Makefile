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
	.venv/bin/python populate_work_items.py --config $(CONFIG) --reset $(if $(FIXTURES),--fixtures $(FIXTURES))
	.venv/bin/python -m factory.runner --config $(CONFIG) &
	.venv/bin/python -m factory.gate_process --config $(CONFIG) &
	.venv/bin/python -m factory.scheduler --config $(CONFIG) &
	wait
	.venv/bin/python -m factory.report --config $(CONFIG)
	.venv/bin/python -m factory.telemetry --config $(CONFIG)
	.venv/bin/python -m factory.telemetry --verify --config $(CONFIG)