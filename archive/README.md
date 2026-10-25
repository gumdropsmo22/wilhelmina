# Wilhelmina historical files

The active Wilhelmina runtime and current maintenance instructions are in the repository root, `cogs/`, `services/`, `config/` and `AGENTS.md` / `README.md`.

- `node/` holds archived legacy Node implementation files.
- The previous root-level C3/C6 PowerShell/CMD reset, rebase, repair and bootstrap scripts and `bot.py.bak` were **removed from the active checkout** during October 2026 repository hygiene. They remain available by commit history and via the explicit `archive/pre-hygiene-2026-10-25` recovery branch at `05f4bac3880d6a98bda228953d32754ad0594cef`.

**Never run historical reset/cleanup scripts against the current checkout.** Restore selectively only after reviewing what they do. For current setup, follow the top-level `README.md`.
