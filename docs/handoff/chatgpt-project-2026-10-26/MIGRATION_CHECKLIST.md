# New ChatGPT Project migration — exact steps and QA

**Goal:** establish a *new ChatGPT Project*, not relocate the runtime repository or change production. You are not required to reorganize or clone GitHub to complete the chat-context migration.

## Setup sequence

- [ ] Download `Wilhelmina_New_Project_Handoff.zip` and inspect `START_HERE.md`, `SOURCE_REGISTER.md` and `MANIFEST_SHA256.txt`; preserve `ORIGINAL_SOURCES/` exactly as received.
- [ ] In ChatGPT sidebar, select **New project**, name it something like **The Bot That Will Become — Wilhelmina**. Optionally choose **Project-only memory** if a deliberately self-contained project is desired; settings/access vary by account. The new project can use only the context accessible under its selected memory mode.
- [ ] Open the project's **••• → Project settings → Instructions** and paste **the complete contents of `NEW_PROJECT_INSTRUCTIONS.md`**, not the outdated proposed AGENTS file. These instructions serve the ChatGPT Project; they do *not* write GitHub `AGENTS.md`.
- [ ] Add `WILHELMINA_PROJECT_CONTEXT_MASTER.md` as the first knowledge file. It consolidates all handoff content to reduce Project file-slot usage. Add `ORIGINAL_SOURCES/AGENTS_Wilhelmina_Proposed.md` and `ORIGINAL_SOURCES/Roadmap .md` if there is space; ideally include all five untouched original sources. Depending on your plan's upload limits, stage files in batches (currently max 10 files uploaded at once per official Help). **Do not assume a ZIP alone will be indexed as its constituent Markdown files; upload the individual files or the combined master.**
- [ ] If moving eligible historical chats is worthwhile, use their chat **Move to project** action. Chats created with a GPT may not be eligible; in that case the uploaded handoff is the continuity path. Project memory need not automatically reference another project's chats.
- [ ] Create a new chat inside that Project; paste `NEW_PROJECT_FIRST_MESSAGE.md` content. Ask it to verify current GitHub before accepting status.
- [ ] Avoid adding `.env`, API keys, SQLite containing member personal data, raw DM messages or screenshots with real secrets merely to recreate technical context.
- [ ] Keep the current authoritative repo links handy: `https://github.com/gumdropsmo22/wilhelmina`, live `AGENTS.md`, README, `docs/testing_phase_checklist.md`, and `docs/maintenance/repo-hygiene-handoff-2026-10-25.md`.
- [ ] Before an actual engineering tranche, explicitly approve a **specific** scope. Reading a handoff is not authorization for a GitHub write, production action or PR merge.

Official ChatGPT Project behavior and settings: https://help.openai.com/en/articles/10169521-projects-in-chatgpt (checked 2026-10-26). Projects can keep chats, files and instructions, and some existing chats can be moved if eligible. File limits and memory settings depend on the account, so do not promise a specific upload capacity.

## Receiving-project acceptance tests

The new assistant must answer all of these **without inventing approval**:

1. **Identity:** Who is Wilhelmina for, and what must her personality *not* become? Must mention one private single-digit-member Discord server and socially specific, profane, hostile-funny character.
2. **Authority:** Who can authorize new product features and repository merges? Must say the founder; implementation approval is not automatically merge approval.
3. **State:** Is PR #39 awaiting merge? Must say no, merged Aug 27 2026. Are phases 5 and 6 built? Yes, merged, with live validation pending.
4. **Consent:** Should `adult_memory_consent` be implemented? No; it was an unapproved design removed from current main (v12 identity).
5. **Age:** Is the project permanently 18+? Must say current under-18 induction behavior exists, final owner decision pending; applicable external content/platform constraints separate.
6. **Collection:** Can Wilhelmina automatically remember all guild conversation? No; current extraction is scoped to approved direct interaction; ambient collection not approved.
7. **Memory:** Distinguish Fact, Inference, Impression, Gossip and source evidence; do not equate rumor with verified fact.
8. **Future:** Name the two still-unbuilt candidate experiences without inventing their specs: evolving social/personality analysis and image generation.
9. **Retirement:** Should `/readings`, `/rituals`, public `/broadcast`, or `/welcome` be built now? No: first three retired, `/welcome` is join-event, not a slash command; real automated broadcasts and `/tarot` are merged.
10. **Proof:** Does green CI equal live Discord/provider acceptance? No. The full final checklist is pending.
11. **Source discipline:** Which `AGENTS` file is canonical? Live GitHub `AGENTS.md`, not `AGENTS_Wilhelmina_Proposed.md`. Where should it resume? Latest current repo and founder's next approved feature/decision, not August Phase 4.

**Failure rule:** If any answer is wrong, point the assistant to the exact current source. Do not compensate by adding generic rules or changing the product to avoid confronting the mismatch.

## What this handoff DOES NOT include

- No historical chat import performed automatically.
- No repository clone; no private GitHub branch access, no local install/test execution.
- No live Discord/provider credential or server setting access.
- No project creation on your behalf.
- No repository mutations, PR merges or branch deletion.

**Ready for pickup when:** project instructions installed, master context uploaded, five originals preserved, starter message used, live status reverified and all receiving-project acceptance tests passed.