.PHONY: install test lint clean build publish

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=wraith --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info/ src/*.egg-info/ .pytest_cache/ .coverage htmlcov/

build:
	python -m build

publish: clean test lint build
	python -m twine upload dist/*
