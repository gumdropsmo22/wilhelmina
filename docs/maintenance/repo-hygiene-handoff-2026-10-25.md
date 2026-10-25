# Repository hygiene handoff — 2026-10-25

This is a **dated operational record**, not a competing product roadmap. For live product authority consult [AGENTS.md](../../AGENTS.md), especially sections 16A and 28, and the root [README](../../README.md).

## Recovery and cleanup changes

- Original main at audit: `05f4bac3880d6a98bda228953d32754ad0594cef` (PR #53 merged, CI green).
- Preserved recovery ref: `archive/pre-hygiene-2026-10-25` at that exact commit. **Do not delete this recovery branch as part of routine hygiene.**
- PR #54: reconciled status/roadmap/docs; **merged**, CI green.
- PR #55: removed retired Help sealed doors and corrected tests; **merged**, CI green.
- PR #57: narrow runtime/SQLite/log/cache ignores and removed `repo-write-test.md`; **merged**, CI green.
- PR #56: relocated 16 C3/C6 bootstrap/repair files into `archive/legacy-tools/early-python-bootstrap` without changing their contents; **open** after its merge action was blocked by connector safety checks despite green exact-head CI. Do not describe the root as fully clean until it merges.
- Issue #40 was triaged with a concrete audit comment; **kept open** pending assessment of its missing doctrine ADR/disclosure/reviewer tests.
- Remote branch deletion and `main` protection were not changed: the available GitHub integration does not expose those mutations. `main` remained unprotected at the time of this audit.

## Original remote branch-head audit

All **46** pre-hygiene non-`main` branches were compared with the then-current `main` using GitHub's compare endpoint. "Behind" means branch tip is an ancestor of main; "diverged" means Git reports commits on both sides, **not necessarily unique substantive functionality** after squashes/rebases. Preserve divergence until exact patch-equivalence review.

### 25 ancestor branches: eligible for routine remote-pruning *after current ref checks*

- `feature-inventory-audit`
- `docs-status-reconcile`
- `feature-tarot`
- `feature-welcome-flow`
- `feature/coven-registry`
- `memory-profile-induction`
- `openai-platform-foundation`
- `phase-1-foundation-reconciliation`
- `phase-2-memory-architecture`
- `phase-3-memory-controls`
- `phase-4-automatic-memory-extraction`
- `phase-6b-chat-prompt-openai`
- `phase-6c-chat-continuity-reliability`
- `phase-6d-chat-hostile-hardening`
- `C1`
- `C2`
- `C3`
- `C5`
- `chore/C1-finalize`
- `chore/C2-layout`
- `cleanup/C7-9`
- `codex/create-/roll-slash-command-with-dice-and-openai-integration`
- `codex/implement-discord-slash-commands-for-oracle`
- `codex/replace-package.json-and-add-.env.example`
- `feat/onboard-command`

### 21 divergent branches: preserve until unique-commit / patch-equivalence audit

- `docs/testing-phase-checklist`
- `feature/broadcast-source-adapters`
- `feature/scheduled-daily-broadcasts`
- `phase-3-remove-memory-consent-gate`
- `phase-4-permanent-memory-cleanup`
- `phase-5-context-intelligence-retrieval`
- `phase-6a-chat-contract-routing`
- `roadmap/runtime-foundation`
- `roadmap/unbundle-divination-runtime`
- `codex/add-centralized-logging-and-error-reporter`
- `codex/create-package.json-for-wilhelmina-bot`
- `codex/implement-default-ephemeral-replies-for-commands`
- `codex/implement-dynamic-/help-command`
- `codex/implement-global-error-handler-for-discord-bot`
- `codex/plan-and-execute-cleanup-tasks-c1-to-c3`
- `codex/plan-and-implement-cleanup-tasks-c7c9`
- `feat/onboarding-ritual-contract`
- `memory-ledger-plan`
- `phase3`
- `phase-4`
- `tmrscg-codex/create-package.json-for-wilhelmina-bot`

The audit above is limited to the **original 46 branches**, not the five hygiene branches created on 2026-10-25. Following merge, `chore/hygiene-docs-2026-10-25`, `fix/hygiene-help-2026-10-25` and `chore/hygiene-runtime-ignore-2026-10-25` are separate completed-PR cleanup candidates; `chore/hygiene-archive-2026-10-25` must remain while PR #56 is open.

## Resume checklist

1. Resolve and merge [PR #56](https://github.com/gumdropsmo22/wilhelmina/pull/56) only after verifying move-only content; connector safety prevented the merge in this session.
2. Configure GitHub `main` branch protection: no force-push/deletion, PR gate and successful CI without requiring a second human reviewer in this owner-operated project.
3. For each ancestor branch, re-check the live SHA/ancestry and PR state, preserve an archive tag if desired, then delete the stale branch. **No bulk deletion**. Review divergent branches individually before any removal.
4. Resolve the remaining actions for [Issue #40](https://github.com/gumdropsmo22/wilhelmina/issues/40); do not close based only on age.
5. Confirm current `main` exact-head CI, run `ruff check .` and `pytest`, and inspect the active root to ensure no legacy C3/C6 scripts remain.
6. Future product docket: **unbuilt** evolving evidence-backed personality/social analysis and **unbuilt** Image Generation (historical design exists; details pending). **Age gate still PRODUCT DECISION PENDING**. Complete broadcast feed configuration, OpenAI private retention and final live Discord/provider QA **after** approved feature work.

No production secrets, private member information or live Discord settings are stored in this audit.
