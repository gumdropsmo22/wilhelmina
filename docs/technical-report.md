# Wilhelmina Discord Bot Technical Report

## 1. Project Identification

**Project name:** Wilhelmina  
**Project type:** Discord application / Discord bot  
**Primary implementation language:** Python  
**Primary framework:** `discord.py`  
**Current repository:** `gumdropsmo22/wilhelmina`  
**Current entrypoint:** `bot.py`  
**Current runtime model:** Single-process asynchronous Discord gateway client

The current repository contains a Python Discord bot using `discord.py`. The entrypoint is responsible for environment loading, Discord client initialization, cog loading, slash command synchronization, and Discord gateway startup.

---

## 2. Current Implementation State

### 2.1 Runtime Bootstrap

Current bootstrap responsibilities:

```txt
- Load environment variables from .env
- Read DISCORD_TOKEN
- Read APP_ENV
- Read DEV_GUILD_ID
- Instantiate discord.ext.commands.Bot
- Load configured cogs
- Sync application commands
- Start Discord gateway session
```

Current limitation:

```txt
Only cogs.core is loaded by the active runtime loader.
Additional cogs exist but are not connected to the runtime loader.
```

### 2.2 Installed Dependencies

Current dependency set includes:

```txt
- discord.py
- python-dotenv
- aiohttp
- aiohappyeyeballs
- aiosignal
- attrs
- frozenlist
- idna
- multidict
- propcache
- typing_extensions
- yarl
```

Missing or likely future dependencies:

```txt
- openai
- aiosqlite, asyncpg, motor, or pymongo
- apscheduler
- pydantic
- pytest
- ruff
- black
```

### 2.3 Existing Command Modules

Existing module: `cogs/oracles.py`

Defined commands:

```txt
/roll
/8ball
/fortune
```

Current status:

```txt
The module exists but is not currently loaded by bot.py.
```

Behavior classification:

```txt
/roll:
- random number generation
- rule-based response selection
- no AI required

/8ball:
- weighted random intent selection
- AI-generated response text
- static fallback required

/fortune:
- AI-generated response text
- static fallback required
```

---

## 3. Project Objective

Build a modular Discord bot with the following technical capabilities:

```txt
- Discord application command handling
- Modular feature loading
- Server onboarding workflow
- Optional server initialization workflow
- User profile collection
- User authorization gating
- Persistent user memory
- Scheduled message delivery
- AI response generation
- Preset response selection
- Randomized response selection
- Administrative controls
- Configuration-driven behavior
- Deployment-ready runtime
- Local development support
- Production deployment support
```

The project should be implemented as a modular system where major features can be enabled, disabled, replaced, or removed without requiring full repository restructuring.

---

## 4. Scope Control

The project should be treated as a feature-flagged system.

Many modules are provisional and should not be hardwired into the core runtime until accepted.

### 4.1 Stable Core Scope

These components should be treated as core infrastructure:

```txt
- Bot bootstrap
- Environment configuration
- Cog loader
- Slash command synchronization
- Logging
- Error handling
- Permission validation
- Database access layer
- User model
- Guild/server model
- Feature flag system
- Admin command group
```

### 4.2 Volatile Feature Scope

These components should be treated as cancellable or replaceable:

```txt
- Existing-server initialization workflow
- New-server provisioning workflow
- Channel archival workflow
- Channel creation workflow
- User access gate workflow
- Direct-message onboarding workflow
- Mood collection workflow
- Scheduled broadcast workflow
- AI chat channel
- Divination commands
- Image-generation command
- Voice-channel activity trigger
- Trial/game/event modules
```

---

## 5. Recommended Architecture

### 5.1 Target Repository Structure

```txt
wilhelmina/
├─ bot.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ pyproject.toml
├─ config/
│  ├─ __init__.py
│  ├─ settings.py
│  ├─ feature_flags.py
│  ├─ constants.py
│  ├─ permissions.py
│  └─ defaults.py
├─ cogs/
│  ├─ __init__.py
│  ├─ core.py
│  ├─ admin.py
│  ├─ onboarding.py
│  ├─ server_init.py
│  ├─ access_control.py
│  ├─ oracles.py
│  ├─ chat.py
│  ├─ broadcasts.py
│  ├─ mood.py
│  ├─ voice.py
│  ├─ images.py
│  └─ diagnostics.py
├─ services/
│  ├─ __init__.py
│  ├─ database.py
│  ├─ memory.py
│  ├─ ai.py
│  ├─ scheduler.py
│  ├─ discord_utils.py
│  ├─ permission_service.py
│  ├─ onboarding_service.py
│  ├─ broadcast_service.py
│  └─ audit_log.py
├─ models/
│  ├─ __init__.py
│  ├─ user_profile.py
│  ├─ guild_config.py
│  ├─ onboarding_state.py
│  ├─ mood_entry.py
│  ├─ memory_record.py
│  └─ audit_event.py
├─ data/
│  └─ local.sqlite3
├─ tests/
│  ├─ test_feature_flags.py
│  ├─ test_oracles.py
│  ├─ test_memory.py
│  └─ test_permissions.py
└─ scripts/
   ├─ run_dev.ps1
   ├─ sync_commands.ps1
   └─ deploy_check.ps1
```

---

## 6. Runtime Design

### 6.1 Entrypoint Responsibilities

`bot.py` should only handle:

```txt
- Environment loading
- Logging setup
- Bot object creation
- Cog loading
- Discord session startup
```

Business logic should be moved into cogs and services.

### 6.2 Feature Flag Loader

Recommended extension loading pattern:

```python
async def load_cogs():
    extensions = {
        "cogs.core": True,
        "cogs.admin": True,
        "cogs.oracles": settings.ENABLE_ORACLES,
        "cogs.onboarding": settings.ENABLE_ONBOARDING,
        "cogs.server_init": settings.ENABLE_SERVER_INIT,
        "cogs.chat": settings.ENABLE_CHAT,
        "cogs.broadcasts": settings.ENABLE_BROADCASTS,
        "cogs.mood": settings.ENABLE_MOOD,
        "cogs.voice": settings.ENABLE_VOICE,
        "cogs.images": settings.ENABLE_IMAGES,
    }

    for extension, enabled in extensions.items():
        if not enabled:
            logger.info("extension_skipped", extra={"extension": extension})
            continue

        try:
            await bot.load_extension(extension)
            logger.info("extension_loaded", extra={"extension": extension})
        except Exception:
            logger.exception("extension_failed", extra={"extension": extension})
```

### 6.3 Feature Flag Configuration

Example `.env` values:

```env
ENABLE_CORE=true
ENABLE_ADMIN=true
ENABLE_ORACLES=false
ENABLE_ONBOARDING=false
ENABLE_SERVER_INIT=false
ENABLE_CHAT=false
ENABLE_BROADCASTS=false
ENABLE_MOOD=false
ENABLE_VOICE=false
ENABLE_IMAGES=false
```

Feature flag benefits:

```txt
- Code can be completed before activation
- Unstable modules can remain disabled
- Production deployment can exclude incomplete features
- Local development can test one module at a time
- Feature cancellation does not require repository deletion
```

---

## 7. Configuration Model

### 7.1 Required Environment Variables

```env
DISCORD_TOKEN=
CLIENT_ID=
APP_ENV=development
DEV_GUILD_ID=
DATABASE_URL=
OPENAI_API_KEY=
```

### 7.2 Optional Environment Variables

```env
LOG_LEVEL=INFO
COMMAND_SYNC_MODE=dev
DEFAULT_TIMEZONE=Asia/Riyadh
ENABLE_ORACLES=false
ENABLE_ONBOARDING=false
ENABLE_SERVER_INIT=false
ENABLE_CHAT=false
ENABLE_BROADCASTS=false
ENABLE_MOOD=false
ENABLE_VOICE=false
ENABLE_IMAGES=false
```

### 7.3 Server-Specific Configuration

Server configuration should be stored in the database instead of only `.env`.

Recommended fields:

```txt
guild_id
guild_name
admin_role_id
member_role_id
pending_role_id
log_channel_id
onboarding_channel_id
chat_channel_id
broadcast_channel_id
mood_channel_id
timezone
features_enabled
created_at
updated_at
```

---

## 8. Data Storage Design

### 8.1 Development Database

Recommended local development database:

```txt
SQLite
```

Rationale:

```txt
- No external database setup
- Lower operational overhead
- Easy backup
- Sufficient for single-server testing
```

### 8.2 Production Database

Recommended production database:

```txt
PostgreSQL via Supabase, Railway, Render, Neon, or similar provider
```

Alternative:

```txt
MongoDB Atlas
```

Use PostgreSQL if structured relational data is expected. Use MongoDB if document-style memory records are prioritized.

---

## 9. Data Model

### 9.1 User Profiles

```sql
CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    onboarding_status TEXT NOT NULL DEFAULT 'pending',
    memory_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (guild_id, user_id)
);
```

### 9.2 Onboarding Contracts

```sql
CREATE TABLE onboarding_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    accepted_at TEXT,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
```

### 9.3 Memory Records

```sql
CREATE TABLE memory_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 9.4 Mood Entries

```sql
CREATE TABLE mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    mood_value TEXT NOT NULL,
    metadata_json TEXT,
    submitted_at TEXT NOT NULL
);
```

### 9.5 Scheduled Jobs

```sql
CREATE TABLE scheduled_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    schedule_expression TEXT NOT NULL,
    channel_id TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 9.6 Audit Events

```sql
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT,
    user_id TEXT,
    event_type TEXT NOT NULL,
    event_payload_json TEXT,
    created_at TEXT NOT NULL
);
```

---

## 10. Module Specifications

### 10.1 Core Module

Status: partially implemented.

Responsibilities:

```txt
- Health/status command
- Uptime command
- Runtime diagnostics
- Slash command sync command
- Version reporting
```

Commands:

```txt
/about
/uptime
/sync
/status
/version
```

Required changes:

```txt
- Convert static status to structured diagnostic output
- Add version metadata
- Add active feature flag report
- Add dependency check command
```

### 10.2 Admin Module

Status: not implemented.

Responsibilities:

```txt
- Feature flag inspection
- Guild configuration inspection
- Channel ID registration
- Role ID registration
- Manual command sync
- Manual onboarding reset
- Manual user state reset
- Manual scheduled-job execution
```

Commands:

```txt
/admin config view
/admin config set
/admin features
/admin user reset
/admin onboarding resend
/admin jobs list
/admin jobs run
/admin diagnostics
```

Permission requirements:

```txt
administrator
manage_guild
manage_roles
manage_channels
```

### 10.3 Oracle Module

Status: partially implemented but not loaded.

Existing commands:

```txt
/roll
/8ball
/fortune
```

Required changes:

```txt
- Add feature flag
- Add cog loader registration
- Fix dependency list
- Correct probability ratios if required
- Add static-only mode
- Add per-command cooldowns
- Add error fallback for AI failure
```

Recommended configuration:

```env
ORACLES_USE_AI=true
ORACLES_STATIC_FALLBACK=true
ORACLE_COOLDOWN_SECONDS=5
```

### 10.4 AI Service Module

Status: utility code exists but should be refactored.

Responsibilities:

```txt
- OpenAI client initialization
- Request construction
- Response parsing
- Timeout control
- Retry control
- Error handling
- Fallback routing
- Cost-control limits
- Per-user rate limits
```

Required service interface:

```python
class AIService:
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        fallback: str | None = None,
    ) -> str:
        ...
```

Required controls:

```txt
- API key validation
- request timeout
- max output length
- rate limiting
- logging without sensitive content
- fallback response on failure
```

### 10.5 Chat Channel Module

Status: not implemented.

Responsibilities:

```txt
- Monitor a configured text channel
- Ignore bot messages
- Ignore non-configured channels
- Build conversation context
- Retrieve user memory if enabled
- Send AI-generated response
- Store optional conversation summary
```

Technical flow:

```txt
message_create event
→ validate guild
→ validate channel_id == configured_chat_channel_id
→ validate author is not bot
→ fetch user profile
→ fetch memory records if enabled
→ construct prompt
→ call AI service
→ send Discord message
→ optionally store memory summary
```

Required Discord intents:

```txt
message_content
guilds
members
messages
```

Risk:

```txt
message_content intent requires enabling privileged intent in Discord Developer Portal.
```

### 10.6 Onboarding Module

Status: not implemented.

Responsibilities:

```txt
- Detect guild member join
- Assign pending role
- Restrict access until onboarding completion
- Send DM or fallback channel prompt
- Present form/modal or button workflow
- Persist submitted data
- Assign member role
- Remove pending role
- Emit audit event
```

Technical flow:

```txt
member_join event
→ create user_profile row
→ assign pending role
→ attempt DM
→ if DM failure, send fallback instruction if possible
→ collect onboarding data
→ validate payload
→ persist onboarding_contract
→ update user_profile.onboarding_status
→ update roles
→ log audit event
```

Volatile implementation option:

```txt
Existing-server gating may be replaced by new-server provisioning or invite-only server onboarding.
```

Design requirement:

```txt
Do not couple onboarding logic to mandatory existing-server transformation.
```

### 10.7 Server Initialization Module

Status: not implemented.

This module should remain optional.

Possible modes:

```txt
MODE_A_EXISTING_SERVER_TRANSFORMATION
MODE_B_NEW_SERVER_PROVISIONING
MODE_C_NO_SERVER_STRUCTURE_MUTATION
```

#### Mode A: Existing Server Transformation

Responsibilities:

```txt
- Inspect current guild channels
- Create archive category
- Move existing channels into archive category
- Create configured channel layout
- Apply permission overwrites
- Create roles if missing
- Register generated IDs in guild_config
```

Risks:

```txt
- irreversible channel permission misconfiguration
- accidental channel relocation
- missing manage_channels permission
- conflict with existing server structure
```

#### Mode B: New Server Provisioning

Responsibilities:

```txt
- Generate recommended server layout
- Provide setup checklist
- Create channels only after explicit admin command
- Store generated channel IDs
```

Risks:

```txt
- Discord bot cannot create an entire Discord server by itself through normal bot permissions
- server owner/admin must create or invite bot into target server
```

#### Mode C: No Server Structure Mutation

Responsibilities:

```txt
- Use manually supplied channel IDs
- Use manually supplied role IDs
- No automatic channel creation
- No automatic archival behavior
```

Recommendation:

```txt
Implement Mode C first.
Implement Mode B second.
Implement Mode A only after confirmed requirement.
```

### 10.8 Access Control Module

Status: not implemented.

Responsibilities:

```txt
- Role assignment
- Role removal
- Permission validation
- Channel permission validation
- Access state verification
- Recovery command for inconsistent states
```

Required checks:

```txt
- Bot role position > managed target roles
- Bot has manage_roles
- Bot has manage_channels
- Bot has send_messages
- Bot has read_message_history
```

State machine:

```txt
unknown
→ pending_onboarding
→ onboarding_submitted
→ active_member
→ suspended
→ removed
```

### 10.9 Broadcast Module

Status: not implemented.

Responsibilities:

```txt
- Scheduled job registration
- Timezone-aware execution
- Channel targeting
- Content generation
- Fallback content
- Manual broadcast trigger
- Broadcast logging
```

Technical flow:

```txt
scheduler tick
→ query enabled guild jobs
→ validate channel
→ build content from template/static/AI
→ send message
→ write broadcast log
→ update scheduled_jobs.last_run_at
```

Required dependencies:

```txt
apscheduler
zoneinfo or pytz
```

Configuration:

```env
ENABLE_BROADCASTS=false
BROADCAST_USE_AI=false
DEFAULT_TIMEZONE=Asia/Riyadh
```

### 10.10 Mood Module

Status: not implemented.

Responsibilities:

```txt
- Schedule mood prompts
- Collect mood entries
- Persist mood data
- Track unanswered prompts
- Trigger timeout follow-up
- Aggregate mood data
```

Data flow:

```txt
scheduled mood prompt
→ send interaction component
→ collect user response
→ persist mood_entries
→ mark prompt completed
→ scheduled timeout check
→ send follow-up if no response
```

Required entities:

```txt
mood_prompt
mood_entry
mood_timeout_event
```

Risk:

```txt
Direct-message delivery is not reliable because users can disable DMs from server members.
```

### 10.11 Tarot Module

Status: not implemented.

Possible implementation types:

```txt
TYPE_STATIC_DECK:
- local tarot card dataset
- random card selection
- preset interpretation text

TYPE_AI_INTERPRETATION:
- local card selection
- AI-generated interpretation
- static fallback

TYPE_EXTERNAL_API:
- call external tarot API
- higher dependency risk
```

Recommendation:

```txt
Use local static deck data.
Add AI-generated interpretation only behind a feature flag.
```

Data file:

```txt
data/tarot_cards.json
```

Commands:

```txt
/tarot layout:single
/tarot layout:three_card
/tarot layout:custom
```

### 10.12 Image Module

Status: not implemented.

Responsibilities:

```txt
- Accept user prompt
- Validate prompt
- Call image-generation service
- Return image attachment or URL
- Log request metadata
- Enforce rate limits
```

Required controls:

```txt
- per-user cooldown
- per-guild cooldown
- maximum prompt length
- blocked prompt categories
- storage policy
- failure fallback
```

Configuration:

```env
ENABLE_IMAGES=false
IMAGE_PROVIDER=openai
IMAGE_MAX_PROMPT_CHARS=1000
IMAGE_COOLDOWN_SECONDS=60
```

### 10.13 Voice Activity Module

Status: not implemented.

Responsibilities:

```txt
- Listen for voice state updates
- Count active users in voice channel
- Detect threshold crossings
- Debounce repeated triggers
- Send configured message to configured channel
```

Technical flow:

```txt
voice_state_update event
→ identify channel
→ count non-bot members
→ compare threshold
→ check cooldown
→ send notification
→ persist trigger event
```

Required intents:

```txt
guilds
voice_states
```

Configuration:

```env
ENABLE_VOICE=false
VOICE_THRESHOLD=3
VOICE_TRIGGER_COOLDOWN_SECONDS=3600
```

---

## 11. Response Generation Strategy

### 11.1 Static Response

Use for:

```txt
- admin commands
- error messages
- permission failures
- setup instructions
- diagnostics
- deterministic system states
```

Advantages:

```txt
- predictable
- low cost
- no external API dependency
- easier testing
```

### 11.2 Randomized Preset Response

Use for:

```txt
- dice result text
- command flavor text
- timeout follow-ups
- simple repeated commands
```

Implementation:

```txt
random.choice(static_list)
weighted random category
seedless random runtime selection
```

### 11.3 AI-Generated Response

Use for:

```txt
- AI chat channel
- optional generated command responses
- optional broadcast segments
- optional memory summaries
```

Required fallback:

```txt
Every AI-generated feature must have static fallback behavior.
```

### 11.4 Hybrid Response

Use for:

```txt
- broadcast templates
- tarot interpretation
- 8-ball responses
- memory summaries
```

Pattern:

```txt
fixed system prompt
+ structured input
+ controlled generation
+ output validation
+ fallback response
```

---

## 12. Permission Model

### 12.1 Basic Bot Permissions

```txt
View Channels
Send Messages
Use Slash Commands
Read Message History
```

### 12.2 Onboarding / Access Control Permissions

```txt
Manage Roles
Manage Channels
Send Messages
View Channels
Read Message History
Use Slash Commands
```

### 12.3 Server Initialization Permissions

```txt
Administrator or:
- Manage Channels
- Manage Roles
- Manage Guild
- View Audit Log
```

Recommendation:

```txt
Use Administrator only in development.
Use explicit least-privilege permissions in production.
```

---

## 13. Discord Gateway Intents

### 13.1 Base Intents

```python
intents = discord.Intents.default()
```

Sufficient for:

```txt
- slash commands
- basic bot ready event
```

### 13.2 Additional Intents

For onboarding:

```python
intents.members = True
```

For AI chat channel:

```python
intents.message_content = True
intents.messages = True
```

For voice triggers:

```python
intents.voice_states = True
```

Recommended final configuration:

```python
intents = discord.Intents.default()
intents.members = settings.ENABLE_ONBOARDING
intents.message_content = settings.ENABLE_CHAT
intents.messages = settings.ENABLE_CHAT
intents.voice_states = settings.ENABLE_VOICE
```

---

## 14. Development Workflow

Recommended strategy:

```txt
1. Stabilize core runtime.
2. Add feature flag loader.
3. Add database service.
4. Add admin diagnostics.
5. Implement modules behind disabled flags.
6. Write tests for pure logic.
7. Enable one feature at a time in development.
8. Validate in private Discord guild.
9. Promote to production configuration.
```

The bot should support incomplete code without exposing incomplete commands.

Implementation method:

```txt
- Feature flags
- Cog-level load isolation
- Command groups per module
- Static fallback for external services
- Admin-only setup commands
```

---

## 15. Testing Strategy

### 15.1 Unit Tests

Test without Discord API:

```txt
- feature flag parsing
- probability distribution helpers
- static response lookup
- memory summarization validators
- database serialization
- guild configuration validation
- permission model validation
```

### 15.2 Integration Tests

Test with Discord test guild:

```txt
- command registration
- role assignment
- channel permission overwrites
- DM failure fallback
- scheduled job execution
- AI fallback behavior
```

### 15.3 Manual Verification Checklist

```txt
- Bot starts with valid token
- Bot fails clearly with missing token
- Commands sync in development guild
- Disabled modules do not register commands
- Enabled modules register commands
- Missing permissions produce actionable errors
- Database tables initialize
- AI failure uses fallback
- Onboarding state persists after restart
- Scheduled jobs survive restart if persisted
```

---

## 16. Deployment Strategy

### 16.1 Local Development

Environment:

```txt
Windows 11
Python 3.11+
Git
VS Code
PowerShell
.env file
SQLite
```

Run command:

```powershell
python bot.py
```

### 16.2 Hosted Development

Recommended platforms:

```txt
Railway
Render
Fly.io
VPS
```

Required environment variables:

```txt
DISCORD_TOKEN
CLIENT_ID
APP_ENV
DEV_GUILD_ID
DATABASE_URL
OPENAI_API_KEY
```

### 16.3 Production

Production requirements:

```txt
- persistent process manager
- external database
- secret manager or environment variable storage
- structured logs
- restart policy
- deployment rollback
- separate development and production Discord applications or guilds
```

---

## 17. CI/CD Recommendation

Recommended GitHub Actions workflow:

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -r requirements.txt
      - run: python -m pip install pytest ruff
      - run: ruff check .
      - run: pytest
```

Deployment should remain manual until the bot has stable configuration, database migrations, and environment separation.

---

## 18. Risk Register

| Risk | Impact | Mitigation |
|---|---:|---|
| Missing Discord permissions | High | Add diagnostics command and startup permission checks |
| Disabled privileged intents | High | Add setup checklist and runtime validation |
| Incomplete cog loading | Medium | Add feature flag loader and load report |
| External AI API failure | Medium | Static fallback for all AI modules |
| Cost from AI usage | Medium | Rate limits, static mode, max token limits |
| Database schema changes | Medium | Migration strategy |
| Channel mutation errors | High | Avoid existing-server mutation until requirement is locked |
| DM onboarding failure | High | Add fallback interaction channel |
| Slash command sync delay | Low | Use dev guild sync during development |
| Overbuilt provisional features | Medium | Keep modules isolated and cancellable |
| Token leakage | Critical | `.env`, `.gitignore`, secret rotation |

---

## 19. Recommended Immediate Engineering Tasks

### Task 1: Add Feature Flag Loader

Modify `bot.py` to load multiple cogs conditionally.

### Task 2: Normalize Environment Variables

Resolve naming mismatch:

```txt
GUILD_ID
DEV_GUILD_ID
CLIENT_ID duplicate entries
```

Use:

```txt
DEV_GUILD_ID
CLIENT_ID
DISCORD_TOKEN
APP_ENV
```

### Task 3: Add Missing Dependencies

Add:

```txt
openai
pydantic
pytest
ruff
```

Add database dependency after choosing backend:

```txt
aiosqlite
```

or:

```txt
asyncpg
```

or:

```txt
motor
```

### Task 4: Add Database Service

Implement:

```txt
services/database.py
services/memory.py
models/user_profile.py
models/guild_config.py
```

### Task 5: Add Admin Diagnostics

Implement:

```txt
/admin diagnostics
/admin features
/admin config view
```

### Task 6: Keep Server Mutation Disabled

Do not implement automatic existing-server channel mutation as a default runtime behavior.

Use:

```env
ENABLE_SERVER_INIT=false
SERVER_INIT_MODE=none
```

### Task 7: Implement Onboarding Without Channel Mutation Dependency

Build onboarding as a standalone module that can operate with manually supplied role/channel IDs.

---

## 20. Recommended Build Order

```txt
Phase 0:
- Repository cleanup
- Dependency correction
- Feature flag loader
- Logging
- Settings normalization

Phase 1:
- Database service
- Guild config storage
- User profile storage
- Admin diagnostics

Phase 2:
- Activate existing oracle commands
- Add static fallback controls
- Add cooldowns
- Add tests

Phase 3:
- Onboarding state machine
- Role gating
- DM/fallback workflow
- Contract persistence

Phase 4:
- AI service abstraction
- Chat channel module
- Memory retrieval
- Memory write controls

Phase 5:
- Scheduler service
- Broadcast module
- Mood module

Phase 6:
- Voice activity module
- Image module
- Optional server initialization module

Phase 7:
- Production deployment
- Monitoring
- Backup strategy
- Operational documentation
```

---

## 21. Technical Conclusion

The project should be implemented as a modular Discord bot with a stable runtime core and optional feature cogs. The current repository has a valid Python Discord bot skeleton, but only the core cog is active. Additional command modules exist but are not connected to the runtime loader. The dependency list does not currently support all referenced or planned functionality.

The correct engineering path is:

```txt
- Stabilize the runtime.
- Add feature flags.
- Add persistence.
- Isolate optional modules.
- Implement provisional features behind disabled flags.
- Avoid irreversible server mutation until the server initialization model is finalized.
- Use static fallback for every AI-dependent feature.
- Treat AI generation, scheduling, onboarding, memory, and server structure as separate services.
```

The existing-server workflow and new-server workflow should be represented as alternative implementation modes, not as hardcoded assumptions.
