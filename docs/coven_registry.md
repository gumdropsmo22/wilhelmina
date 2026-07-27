# The Coven Registry

The Coven Registry is Wilhelmina's persistent member ledger. It replaces a generic welcome-message flow with a numbered coven induction system and creates the profile shell that future memory features can extend.

## Coven Marks

- `WTCH-0000` is permanently reserved for Wilhelmina.
- `WTCH-0001` is permanently reserved for the founder who runs bootstrap.
- `WTCH-0002` onward are assigned to human members.
- The canonical database value is `WTCH-0002`.
- Discord displays the mark as `⛧WTCH-0002⛧`.
- Marks are permanent and are not recycled when someone leaves.

## Lifecycle

1. An administrator runs `/registry-admin bootstrap`.
2. Wilhelmina and the founder receive the two reserved entries.
3. A human member joining the home guild receives a `Pending` entry and an empty profile shell.
4. Covenant Gate acceptance changes `Pending` to `Initiate`.
5. A public induction notice is posted once when a Registry channel is configured.
6. Departure archives the entry instead of deleting it.
7. Rejoining reactivates the existing entry and preserves the Coven Mark.

The Registry does not assign roles in this phase.

## Classifications

- `Pending`
- `Initiate`
- `Recognized`
- `Bound`
- `Archived`
- `Banished`

## Visibility and privacy

Public commands expose only the Coven Mark, display name, classification, status, and induction timestamp.

Administrator commands expose the full operational file: Discord user ID, Registry number, join/departure timestamps, covenant version linkage, notice message ID, and persistence timestamps.

The profile shell itself contains no inferred traits, conversation surveillance, personality judgments, likes, dislikes, or automatic notes. The separate [Memory Ledger](memory_ledger.md) defines the private memory layer, its administration controls, receipts, deletion behavior, and reveal boundary.

## Commands

Public:

```text
/registry index
/registry me
```

Administrator-only:

```text
/registry-admin bootstrap
/registry-admin status
/registry-admin register
/registry-admin lookup
/registry-admin backfill
/registry-admin set-classification
/registry-admin set-status
/registry-admin set-channel
/registry-admin publish
```

## Setup order

1. Enable the Covenant Gate (`ENABLE_RULES=true`).
2. Enable the Discord Server Members Intent in the Discord Developer Portal.
3. Restart Wilhelmina so application commands synchronize.
4. Run `/registry-admin bootstrap` as the founder.
5. Run `/registry-admin set-channel` for public induction notices.
6. Use `/registry-admin status` to confirm `WTCH-0000`, `WTCH-0001`, and next number `2`.

## Deferred live testing

Manual Discord testing remains part of the final testing phase. The later pass must verify bootstrap idempotency, numbering, joins, covenant induction, one-time notices, public/private visibility, archival, rejoin behavior, backfill order, restart persistence, and the absence of role mutation.
