# StadiumMind - convenience targets. Mirrors exactly what CI runs
# (.github/workflows/tests.yml) so `make lint && make typecheck && make test`
# locally is the same pass/fail signal as the GitHub Actions checks.
#
# Usage: make <target>   e.g. make test

.PHONY: install install-dev lint typecheck test coverage run clean

install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt

lint:
	ruff check .

typecheck:
	mypy .

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=core --cov=agents --cov-report=term-missing

run:
	streamlit run app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage