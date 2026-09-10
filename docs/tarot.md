# Tarot

Status: **BUILT on feature branch; live Discord/provider validation remains deferred.**

Tarot is a standalone divination feature. It does not belong to the legacy Oracle umbrella and it does not persist reading history or automatically create Memory Ledger records.

## Approved product contract

- `/tarot single` draws one card.
- `/tarot three` draws three distinct cards in **Past / Present / Future** order.
- Both commands accept an optional question.
- The member chooses **Public** or **Private** when invoking the command.
- Public responses post normally in the interaction channel.
- Private responses use Discord ephemeral interaction responses; Tarot does not invent a DM delivery path.
- Reversals are enabled from the first release. Every selected card receives an independent upright/reversed decision.
- The canonical deck contains 78 cards: 22 Major Arcana and 56 Minor Arcana.
- No card may appear twice inside one three-card spread.
- Each reading starts fresh from the complete deck. A card appearing in a later reading is allowed and is not artificially suppressed.
- Card selection and orientation are local application decisions. OpenAI interprets a frozen draw and may not redraw, replace, reorder, add, remove, or flip cards.
- If the provider is unavailable or its output fails the hard-secret boundary, the same frozen draw receives a deterministic local fallback reading.
- Tarot is stateless. There is no Tarot-specific history table, daily-card state, or automatic memory.
- `ENABLE_TAROT=false` by default. Live activation is deferred until final project-wide validation.

## Draw engine

`services.tarot` owns the canonical deck and draw rules.

Production draws use Python `random.SystemRandom`, backed by the operating system randomness source. A three-card reading samples without replacement, which guarantees three distinct cards inside that spread. Orientation is an independent one-bit decision per card.

Automated tests inject a deterministic fake random source. Production never uses that test source or a fixed seed.

## Interpretation boundary

The draw is completed locally before any provider request.

The provider receives structured data containing the spread type, optional question, exact card IDs and names, exact positions, exact upright/reversed orientations, and local keywords for the selected orientation.

Trusted Wilhelmina persona and Tarot rules are sent separately from the untrusted question payload. The shared async OpenAI provider boundary is reused with response storage forced off. Tarot does not require the Memory Ledger or chat continuity system.

Generated output is checked against the existing narrow hard-secret boundary before Discord clipping/presentation. Provider failure never triggers a redraw.

## Artwork plugin

Artwork is optional presentation only. The feature works completely without it.

By default the renderer looks under `assets/tarot/`. `TAROT_ARTWORK_DIR` may point elsewhere. Each card has a stable artwork key, for example `major/00_the_fool`, `cups/ace_of_cups`, or `swords/queen_of_swords`. Supported extensions are PNG, JPG/JPEG, and WEBP.

If artwork exists, it is attached to the same Discord response. Reversed cards are rotated 180 degrees when the optional Pillow dependency is installed with `pip install -e '.[tarot-artwork]'`.

Without Pillow, reversed readings still work and are clearly labelled `Reversed`; the source artwork is displayed in its original orientation rather than making image support a hard dependency.

## Deferred work

The first Tarot tranche intentionally does not add saved reading history, automatic memory of readings, daily cards, Celtic Cross or larger spreads, alternative decks, DMs, elaborate animation, `/readings` behavior, or `/rituals` behavior.

Custom artwork can be added later without changing the deck or interpretation engine.

## Final validation

Do not move live testing forward. During the final whole-project validation stage, verify command sync and option presentation, public vs ephemeral delivery, actual OpenAI interpretation quality, fallback behavior, artwork attachments, reversal rotation, and one-card/three-card Discord rendering.
