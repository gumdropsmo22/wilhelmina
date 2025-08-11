# Wilhelmina Bot
Python-only runtime (cleanup sprint).

The Node implementation has been archived under `archive/node/`. From now on,
all runtime and development commands use Python tooling only. See `pyproject`/`requirements`
and `Makefile` at the repo root.

> Historical JS/TS code and npm scripts are preserved in `archive/node/`
> but are **not** part of the build or CI anymore.

## Installation (Python)
See `Makefile` for common tasks:
```
make venv        # create venv
make install     # install Python deps
make run         # run the bot
```

## Quickstart
```bash
make install
make run
```

## Developer scripts
```bash
make fmt    # black
make lint   # ruff
make type   # mypy (loose; tightened later)
make test   # pytest
```

## Environment
Provide `DISCORD_TOKEN` in your shell or `.env`. (C4 will add `.env.example` refinement.)

## Node (archived)
If you need the previous Node prototype, consult `archive/node/README.md`.
It is **unsupported** and excluded from CI.
