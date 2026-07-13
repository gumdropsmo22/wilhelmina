# Scheduled Daily Broadcasts

Scheduled Daily Broadcasts is Wilhelmina's automatic two-segment show system.

## Segments

| Segment | Title | Default time | Timezone | Status |
|---|---|---:|---|---|
| `morning` | The Vanguard Frequency | 08:00 | Asia/Riyadh | disabled by default |
| `evening` | W.W.N. Broadcast | 21:30 | Asia/Riyadh | disabled by default |

## Creative contracts

### Morning: The Vanguard Frequency

The morning segment is a gritty, defiant, pro-worker broadcast. It should use verified daily headlines about labor, economics, corporate power, and geopolitical struggle. It must not use generic morning tropes. It must not fabricate headlines, statistics, sponsors, weather, traffic, or sky data.

Required sections:

```txt
TRANSMISSION INITIATION
THE MATERIAL CONDITIONS
THE TACTICAL SKY
END OF TRANSMISSION
```

### Evening: W.W.N. Broadcast

The evening segment is a deadpan late-night Witch Watch Network dispatch. It mixes factual news with dark, cynical, supernatural commentary. The factual layer must still come only from verified source packets.

Required sections:

```txt
OPENING TRANSMISSION
NEWS OF THE NIGHT
PLANETARY FORECAST
CLOSING INCANTATION
```

## Runtime behavior

The scheduler checks the configured home guild once per minute. When a segment's local time matches the configured `HH:MM`, the cog claims a scheduled run for that guild, segment, and local date. The unique scheduled-run key prevents duplicate posts after restarts or repeated ticks.

Scheduled runs require both:

```txt
at least one verified news headline
ready Riyadh sky data
```

If those are missing, the run is marked `skipped` with `missing_required_sources`. Preview and test commands still render deterministic fallback copy so admins can test the Discord surface safely.

## Storage

The feature adds these SQLite tables:

```txt
broadcast_settings
broadcast_runs
broadcast_text_history
```

`broadcast_settings` stores channel overrides, enablement, local times, timezone, provider names, and category lists.

`broadcast_runs` stores scheduled/test execution history, message IDs, fallback use, and failure codes.

`broadcast_text_history` stores opener, closer, and full-message hashes for anti-repetition checks.

## Admin commands

```txt
/broadcast-admin status
/broadcast-admin preview segment:<morning|evening>
/broadcast-admin send-test segment:<morning|evening> [channel]
/broadcast-admin enable segment:<morning|evening|all>
/broadcast-admin disable segment:<morning|evening|all>
/broadcast-admin set-channel target:<default|morning|evening> channel:#channel
/broadcast-admin set-time segment:<morning|evening> time:HH:MM
/broadcast-admin set-timezone timezone:Asia/Riyadh
```

## Source adapters

The source layer currently supports generic RSS/Atom feeds plus computed moon data for Riyadh.

Environment variables:

```env
BROADCAST_NEWS_RSS_URLS=
BROADCAST_ASTRONOMY_RSS_URLS=
BROADCAST_NEWS_MAX_ITEMS=4
BROADCAST_ASTRONOMY_MAX_ITEMS=2
BROADCAST_SOURCE_TIMEOUT_SECONDS=10
```

`BROADCAST_NEWS_RSS_URLS` and `BROADCAST_ASTRONOMY_RSS_URLS` are comma-separated. Feed items are normalized into `Article` evidence records, category-filtered, then passed into the generation prompt.

The sky adapter computes the current moon phase and illumination for the configured timezone. It does not invent meteor showers, eclipses, or planetary visibility; those are only added when an astronomy feed reports them.

## Provider policy

Wilhelmina may style, analyze, and mock the evidence. She may not create the evidence. Missing source data must result in omission, fallback, or skipped scheduled runs.

Future provider adapters can be added behind the same source interface without changing the broadcast scheduler or command surface.
