.PHONY: lint format test cov audit check

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