# Testing Phase Checklist

This is the living checklist for Wilhelmina's final testing phase.

Do not treat this as a signal to test everything immediately. The project is still in creation mode. This document exists so every finished feature has a place in the later full-system QA pass instead of relying on memory, optimism, or whatever haunted fog GitHub was breathing that day.

## Testing phase rule

The full manual testing phase happens **after** the current creation/build phase is complete.

Until then:

- add new features to this checklist as they are created;
- add new setup requirements when features gain configuration;
- add regression checks whenever a bug is fixed;
- do not remove items just because they passed once in CI;
- keep CI/unit tests separate from final Discord live testing.

## Current automated baseline

Run these before live Discord testing:

```bash
ruff check .
pytest
```

Expected result:

```txt
lint = pass
tests = pass
```

## Environment and deployment readiness

| Check | Expected result | Status |
|---|---|---|
| Python environment installs with `python -m pip install -e ".[dev,ai]"` | install completes | Pending final test |
| `.env` has `DISCORD_TOKEN` | bot can authenticate | Pending final test |
| `.env` has `CLIENT_ID` | slash command sync can target app | Pending final test |
| `.env` has `HOME_GUILD_ID` | bot locks to home guild | Pending final test |
| `COMMAND_SYNC_MODE=guild` | commands sync quickly to home guild | Pending final test |
| `DATABASE_PATH` points to writable SQLite path | database initializes | Pending final test |
| Required cogs enabled | `cogs.core` and `cogs.admin` load | Pending final test |
| Optional feature flags match intended launch state | only intended features load | Pending final test |
| Bot starts without tracebacks | runtime stays online | Pending final test |
| Slash commands are visible in Discord | all enabled commands appear | Pending final test |

## Database and persistence

| Check | Expected result | Status |
|---|---|---|
| SQLite file is created when missing | `data/wilhelmina.sqlite3` or configured path exists | Pending final test |
| Schema migrations table exists | `schema_migrations` populated | Pending final test |
| Guild config persists after restart | configured values survive restart | Pending final test |
| Audit log records admin changes | config/rules/broadcast actions are logged | Pending final test |
| Rules acceptance persists after restart | accepted user remains accepted | Pending final test |
| Broadcast settings persist after restart | schedule/channel settings survive restart | Pending final test |
| Broadcast run history persists | posted/skipped/test runs are recorded | Pending final test |

## Core commands

| Command | Checks | Status |
|---|---|---|
| `/about` | responds successfully; copy is readable; no admin-only data leak | Pending final test |
| `/uptime` | responds successfully; uptime appears reasonable | Pending final test |

## Admin diagnostics and setup

| Command | Checks | Status |
|---|---|---|
| `/admin diagnostics` | shows app env, server mode, sync mode, database path, loaded/skipped/failed cogs | Pending final test |
| `/admin features` | accurately lists enabled/disabled feature flags | Pending final test |
| `/admin sync` | resyncs commands in configured guild | Pending final test |
| `/admin setup status` or readiness commands | identifies missing config clearly | Pending final test |
| Non-admin use of admin commands | rejected ephemerally | Pending final test |
| Admin command outside home guild | rejected safely | Pending final test |

## Admin configuration

| Command | Checks | Status |
|---|---|---|
| `/admin config view` | shows current config with unset fields clearly | Pending final test |
| `/admin config set-role` | saves valid role ID; rejects invalid target | Pending final test |
| `/admin config set-channel` | saves valid channel ID; supports broadcast channel | Pending final test |
| `/admin config set-timezone` | accepts valid IANA timezone; rejects invalid timezone | Pending final test |
| `/admin config validate` | reports missing roles/channels/timezone issues | Pending final test |
| `/admin config clear` | clears selected values without damaging unrelated config | Pending final test |
| Config audit trail | before/after snapshots are recorded | Pending final test |

## Living Command Grimoire

| Command | Checks | Status |
|---|---|---|
| `/help` private default | opens ephemeral grimoire | Pending final test |
| `/help public:true` | posts public grimoire when requested | Pending final test |
| Category dropdown | switches category correctly | Pending final test |
| Pagination buttons | next/previous work; disabled at edges | Pending final test |
| Admin commands hidden | admin-only commands do not appear in public help | Pending final test |
| Optional disabled commands | hidden or shown only as intended future sealed doors | Pending final test |
| AI unavailable fallback | deterministic intro appears | Pending final test |
| AI available intro | short persona-polished line appears without listing commands | Pending final test |

## Covenant Gate rules UI

| Command/Flow | Checks | Status |
|---|---|---|
| `/rules` with no active rules | returns clear fallback | Pending final test |
| `/rules-admin set` | creates a rules version | Pending final test |
| `/rules-admin preview` | previews stored rules without publishing | Pending final test |
| `/rules-admin activate` | marks one active rules version | Pending final test |
| `/rules-admin publish` | posts rules panel with accept button | Pending final test |
| Accept covenant button | records acceptance once | Pending final test |
| Repeated acceptance | reports already accepted without duplicate damage | Pending final test |
| `/rules-admin summary` | shows acceptance summary | Pending final test |
| `/rules-admin user` | shows a specific user's acceptance state | Pending final test |
| `/rules-admin list` | lists stored rules versions | Pending final test |
| Restart persistence | published panel and acceptance state still work after restart where supported | Pending final test |
| Role mutation boundary | accepting rules does not assign roles yet | Pending final test |

## Invite helper

| Command | Checks | Status |
|---|---|---|
| `/invite` | returns usable bot invite or authorization helper | Pending final test |
| Missing `CLIENT_ID` | fails gracefully with setup guidance | Pending final test |
| Output privacy | no token or secret exposure | Pending final test |

## Divination and utility commands

| Command | Checks | Status |
|---|---|---|
| `/roll` | rolls valid dice; rejects invalid dice safely | Pending final test |
| `/roll` copy | output is readable and in Wilhelmina style without blocking the result | Pending final test |
| `/8ball` | answers question; fallback works if AI unavailable | Pending final test |
| `/fortune` | returns fortune-cookie-style output; fallback works if AI unavailable | Pending final test |
| Optional feature flags | disabled divination cogs do not load commands | Pending final test |
| Legacy `ENABLE_ORACLES` shim | enables old split commands only as expected | Pending final test |

## Persona Engine regression checks

| Check | Expected result | Status |
|---|---|---|
| Base voice present | Wilhelmina remains sharp, coherent, useful, and hostile-funny | Pending final test |
| Hard boundary | no mother/mom/mama/mommy/maternal jokes appear | Pending final test |
| No old terminology | no user-facing or prompt-facing `Voice channel` architecture returns | Pending final test |
| No word salad | output avoids random noun-smashing and incoherent occult filler | Pending final test |
| Function first | the actual answer/action is not replaced by a joke | Pending final test |
| AI outage | each AI-backed feature has deterministic fallback | Pending final test |
| Discord length limits | generated outputs do not exceed safe message/embed limits | Pending final test |

## Scheduled Daily Broadcasts

### Configuration

| Command/Setting | Checks | Status |
|---|---|---|
| `ENABLE_BROADCASTS=true` | `cogs.broadcasts` loads | Pending final test |
| `/broadcast-admin status` | shows settings and recent runs | Pending final test |
| `/broadcast-admin set-channel target:default` | stores default broadcast channel | Pending final test |
| `/broadcast-admin set-channel target:morning` | stores morning override channel | Pending final test |
| `/broadcast-admin set-channel target:evening` | stores evening override channel | Pending final test |
| `/broadcast-admin set-time segment:morning time:08:00` | stores morning time | Pending final test |
| `/broadcast-admin set-time segment:evening time:21:30` | stores evening time | Pending final test |
| `/broadcast-admin set-timezone timezone:Asia/Riyadh` | stores Riyadh timezone | Pending final test |
| `/broadcast-admin enable segment:all` | enables both scheduled segments | Pending final test |
| `/broadcast-admin disable segment:all` | disables both scheduled segments | Pending final test |
| Non-admin broadcast commands | rejected ephemerally | Pending final test |

### Preview and test send

| Command | Checks | Status |
|---|---|---|
| `/broadcast-admin preview segment:morning` | renders The Vanguard Frequency preview | Pending final test |
| `/broadcast-admin preview segment:evening` | renders W.W.N. Broadcast preview | Pending final test |
| `/broadcast-admin send-test segment:morning` | posts test message to configured/override channel | Pending final test |
| `/broadcast-admin send-test segment:evening` | posts test message to configured/override channel | Pending final test |
| Missing channel | send-test returns clear error | Pending final test |
| Test run history | test send records run and message ID | Pending final test |

### Source adapters

| Source area | Checks | Status |
|---|---|---|
| Empty RSS settings | scheduled run skips instead of inventing headlines | Pending final test |
| `BROADCAST_NEWS_RSS_URLS` configured | news articles are parsed into evidence | Pending final test |
| `BROADCAST_ASTRONOMY_RSS_URLS` configured | astronomy articles are parsed into evidence | Pending final test |
| Multiple RSS URLs | items combine without crashing | Pending final test |
| Bad RSS URL | failure is noted without taking bot down | Pending final test |
| Slow RSS URL | timeout works | Pending final test |
| Category filtering | labor/economics/corporate/geopolitical items are preferred for morning | Pending final test |
| Evening categories | corporate/environment/politics/world items are usable for evening | Pending final test |
| Computed moon data | Riyadh moon phase and illumination are included | Pending final test |
| No invented sky events | meteor showers/eclipses/planet visibility are omitted unless source evidence exists | Pending final test |

### Automatic scheduling

| Flow | Checks | Status |
|---|---|---|
| Morning schedule | posts around 08:00 Asia/Riyadh when enabled and sourced | Pending final test |
| Evening schedule | posts around 21:30 Asia/Riyadh when enabled and sourced | Pending final test |
| Duplicate protection | bot does not double-post same segment/date | Pending final test |
| Restart before scheduled time | still posts once | Pending final test |
| Restart after scheduled time | does not spam missed duplicate posts | Pending final test |
| Disabled segment | does not post | Pending final test |
| Run history | scheduled run records posted/skipped/failed state | Pending final test |
| Text history | message hashes are stored for anti-repetition tracking | Pending final test |

### Broadcast content quality

| Segment | Checks | Status |
|---|---|---|
| Morning title/structure | includes The Vanguard Frequency sections | Pending final test |
| Morning tone | gritty, defiant, pro-worker, analytical | Pending final test |
| Morning factuality | factual summaries are sourced; commentary is separated | Pending final test |
| Morning anti-repetition | avoids generic coffee/waking up/Monday clichés | Pending final test |
| Evening title/structure | includes W.W.N. Broadcast sections | Pending final test |
| Evening tone | deadpan, dark, late-night, anti-capitalist, dreadful | Pending final test |
| Evening factuality | news facts come from evidence packet | Pending final test |
| Evening field segment | Field Wilhelmina feels distinct without inventing factual location claims that matter | Pending final test |
| Length | stays under Discord-safe message length | Pending final test |

## Cross-feature regression pass

| Check | Expected result | Status |
|---|---|---|
| All enabled cogs load together | no extension load failures | Pending final test |
| Slash command names do not collide | command sync succeeds | Pending final test |
| Admin-only commands stay admin-only | no public access | Pending final test |
| Ephemeral commands stay ephemeral | private admin/config output not public | Pending final test |
| Database writes do not corrupt each other | config, rules, onboarding, broadcasts coexist | Pending final test |
| Bot restart test | key features still work after restart | Pending final test |
| Missing AI key test | AI-backed features degrade gracefully | Pending final test |
| Present AI key test | AI-backed features generate without breaking rules | Pending final test |
| Missing optional feature flag test | disabled cogs do not expose commands | Pending final test |
| Logging sanity | failures are logged without leaking secrets | Pending final test |

## Later features to add when created

These are placeholders. Expand them when the feature actually exists.

| Future area | Testing notes to add later |
|---|---|
| Welcome messages | join flow, configured channel, role/state assumptions, fallback copy |
| Role automation | rules acceptance consumption, permission safety, idempotent role assignment |
| Tarot/readings/rituals | command flow, AI fallback, tone boundaries, cooldowns if added |
| AI chat/open chat | channel gating, prompt boundaries, memory policy, abuse limits |
| Memory/ledger | opt-in/out behavior, stored data review, deletion, privacy boundaries |
| Reminders/scheduler expansion | timezone behavior, duplicate prevention, missed-run handling |

## Final sign-off template

Use this when the testing phase is actually performed.

```txt
Test date:
Tester:
Bot commit SHA:
Discord server:
Environment:

Automated checks:
- ruff:
- pytest:

Manual Discord checks:
- Core:
- Admin/config:
- Help:
- Rules:
- Invite:
- Divination:
- Persona:
- Broadcasts:

Known failures:
- 

Fixes required before launch:
- 

Launch readiness:
- Not ready / Ready with caveats / Ready
```
