# Environment & Secrets (C4)

Use .env for local dev. Do not commit real secrets.

## Required (now)
- DISCORD_TOKEN: Discord bot token.

## Optional (placeholders for future tasks)
- OPENAI_API_KEY: used in C10 when AI wiring lands.
- MONGO_URL: used when persistence lands.
- TZ: default Asia/Riyadh; used when jobs are scheduled later.

## Loading
config/secrets.py loads .env if present and exposes get_secrets().
config/settings.py reads from get_secrets() to construct runtime settings.

## Git hygiene
.env is ignored via .gitignore. Use .env.example to document keys.
