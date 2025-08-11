PY?=python3
VENV?=.venv
PIP?=$(VENV)/bin/pip
PYBIN?=$(VENV)/bin/python
PRECOMMIT?=$(VENV)/bin/pre-commit

.PHONY: venv install run fmt lint type test

venv:
$(PY) -m venv $(VENV)

install: venv
$(PIP) install -U pip
$(PIP) install -r requirements.txt
$(PIP) install pre-commit
$(PRECOMMIT) install
@echo "pre-commit installed & hooks activated."

run:
$(PYBIN) bot.py
