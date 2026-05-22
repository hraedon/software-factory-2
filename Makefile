.PHONY: lint format test cov audit check golden-run integration smoke

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
	$(VULTURE) src/factory/ tests/ .vulture_whitelist.py --min-confidence 80 --exclude "tests/fixtures/capability-probe"

check: lint audit test

integration:
	$(PYTEST) tests/ -q -m integration

golden-run:
	@test -n "$(CONFIG)" || (echo "CONFIG=<path> required" && exit 1)
	.venv/bin/python scripts/golden_run_nanny.py --config $(CONFIG) --populate $(if $(FIXTURES),--fixtures $(FIXTURES))
	.venv/bin/python -m factory.telemetry --config $(CONFIG)
	.venv/bin/python -m factory.telemetry --verify --config $(CONFIG)

smoke:
	@echo "=== Smoke test: 5-item pipeline with cheap model ==="
	.venv/bin/python scripts/agent_golden_run.py \
		--config .factory/smoke-config.yaml \
		--fixtures tests/fixtures/csv-toolkit \
		--log-prefix smoke
	@echo "=== Smoke test complete ==="