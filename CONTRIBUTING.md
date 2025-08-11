# Contributing

## Workflow
- Create a branch per task (e.g., `cleanup/C7-tests`).
- Use Conventional Commits for titles/messages.
- Open PRs; **do not merge** until review is done.

## Dev setup
```bash
make install
pre-commit install
pre-commit run --all-files
make type
make test
```

## Environment
- Copy `.env.example` → `.env`. Never commit real secrets.
- For this cleanup sprint we **do not** add schedulers or finalize AI; any OpenAI usage must go through `utils/ai.py` or be marked `# STUB:`.

## Style & Quality
- Formatting: Black.
- Lint: Ruff.
- Types: MyPy (loose now; can tighten later).
- Embeds: all bot output must go through `utils/embeds.py` and `utils/persona.py`. The only exception is `#chat-with-wilhelmina`.

## Tests
- Keep tests fast and offline. No network or Discord API calls in unit tests.
- Place files under `tests/` and name `test_*.py`.
