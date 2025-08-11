PY?=python3
VENV?=.venv
PIP?=$(VENV)/bin/pip
PYBIN?=$(VENV)/bin/python

.PHONY: venv install run fmt lint type test

venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@echo "Virtualenv ready at $(VENV)"

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

run:
	$(PYBIN) bot.py

fmt:
	$(VENV)/bin/black .

lint:
	$(VENV)/bin/ruff check .

type:
	$(VENV)/bin/mypy --ignore-missing-imports .

test:
	$(VENV)/bin/pytest -q
