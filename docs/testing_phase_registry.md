# Coven Registry — Final Testing Addendum

This checklist belongs to the deferred full-system manual testing phase. Automated tests and CI may run during development; live Discord verification waits for final QA.

| Check | Expected result | Status |
|---|---|---|
| Discord Server Members Intent enabled | join and leave events reach Wilhelmina | Pending final test |
| `/registry-admin bootstrap` first run | creates `WTCH-0000` for Wilhelmina and `WTCH-0001` for founder | Pending final test |
| Bootstrap repeated | remains idempotent and does not allocate new marks | Pending final test |
| Founder identity protection | a different administrator cannot replace the recorded founder | Pending final test |
| `/registry-admin status` after bootstrap | next number is `2`; totals include Wilhelmina and founder | Pending final test |
| Human member joins | receives permanent `Pending` entry and profile shell | Pending final test |
| Bot account joins | no human Registry entry is created | Pending final test |
| Multiple joins close together | Coven Marks remain unique and sequential | Pending final test |
| Member accepts active covenant | `Pending` becomes `Initiate` | Pending final test |
| Repeated covenant acceptance | induction remains idempotent | Pending final test |
| Registry channel configured | one public induction notice is posted | Pending final test |
| Acceptance repeated after notice | no duplicate induction notice appears | Pending final test |
| `/registry index` | shows ordered public entries with no private operational fields | Pending final test |
| `/registry me` | shows only caller's public card | Pending final test |
| `/registry-admin lookup user:` | administrator sees full operational file | Pending final test |
| `/registry-admin lookup mark:` | accepts `WTCH-0002` and `⛧WTCH-0002⛧` | Pending final test |
| Non-admin Registry-admin command | rejected ephemerally | Pending final test |
| `/registry-admin register` | creates or refreshes Pending entry without changing mark | Pending final test |
| `/registry-admin backfill` | existing humans are registered deterministically | Pending final test |
| `/registry-admin set-classification` | valid classification persists and is audited | Pending final test |
| `/registry-admin set-status` | active/archive/banished state persists and is audited | Pending final test |
| Member leaves | entry is archived rather than deleted | Pending final test |
| Archived member rejoins | original Coven Mark is preserved | Pending final test |
| Restart persistence | settings, marks, classifications, shells, and notice IDs survive | Pending final test |
| Role boundary | Registry performs no role assignment or permission mutation | Pending final test |
| Memory boundary | profile shell contains no inferred traits or automatic notes | Pending final test |
| Gothic presentation | headers render acceptably on desktop/mobile while IDs remain copyable | Pending final test |
| Missing Registry channel | induction persists without crashing; notice can be published later | Pending final test |
| Audit trail | bootstrap, registration, induction, classification, status, and channel changes are recorded | Pending final test |
