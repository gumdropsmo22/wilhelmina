# Changelog
All notable changes are listed here. This file is **append-only**. Keep new entries under **Unreleased** until the PR merges.

## Unreleased
- C1: Archived Node runtime under `archive/node/`; Python-only root runtime.
- C2: Established Python layout; centralized `utils/embeds.py` + `utils/persona.py`; minimal oracles added.
- C3: Added requirements/Makefile/pytest.ini.
- C4: Added `.env.example`, centralized `config/secrets.py`, and `docs/ENV.md`.
- C5: Added `.pre-commit-config.yaml`, `ruff.toml`, `mypy.ini`, `.editorconfig`; wired hooks in Makefile.
- C6: Added `utils/logging.py` and wired JSON logging/error capture in `bot.py`.
- C7: Added smoke tests for embeds + oracle helpers.
- C8: Added `CONTRIBUTING.md` and this `CHANGELOG.md`.
- C9: Added GitHub Actions workflow for lint/type/tests.

## 0.0.0 — prehistory
- Initial experiments and Node prototype.
