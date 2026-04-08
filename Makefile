.PHONY: lint format

DEV_PACKAGES := ruff black isort mypy

lint:
	python -m pip install --upgrade pip
	pip install $(DEV_PACKAGES)
	ruff check .
	black --check .
	isort --check-only .
	mypy --config-file mypy.ini app

format:
	pip install $(DEV_PACKAGES)
	ruff check --fix . || true
	black .
	isort .
	# mypy is static analysis only, no formatting step
