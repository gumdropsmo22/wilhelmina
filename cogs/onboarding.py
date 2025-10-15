# cogs/onboarding.py
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import json
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from zoneinfo import ZoneInfo

# =========================
# ====== CONFIG / UX ======
# =========================

PRIMARY_HEX = 0x6B46C1  # #6B46C1
ACCENT_HEX   = 0x00FFFF  # cyan (occasional)
ACCENT2_HEX  = 0x00FF7F  # green (occasional)
FOOTER_TEXT  = "⛧ Wilhelmina // Grand Coven"
DIVIDER      = "⎯⎯⎯⟐⎯⎯⎯"
TZ_DEFAULT   = os.getenv("TIMEZONE", "Asia/Riyadh")

# Ritual pacing (aggressive attention defaults)
EVERYONE_MAX_TOTAL = 6
EVERYONE_MIN_GAP_S = 60
PER_BEAT_MEMBER_MENTIONS = 6
PER_RITUAL_MEMBER_MENTIONS_MAX = 36
RITUAL_DURATION_S = 13 * 60
RITUAL_JITTER_RANGE = (7, 15)  # seconds
RESUME_WINDOW_S = 30 * 60

# Channels (exact names & order)
CHANNELS_ORDERED = [
    ("⛧-000 ⛧-summoning-circle",         {"read_only": True,  "key": "circle"}),
    ("⌬-001 ⌬-node-000-witch-in-the-machine", {"read_only": True}),
    ("⟁-002 ⟁-node-001-wilhelmina",      {"read_only": False}),
    ("⌁-003 ⌁-node-007-the-oracle",      {"read_only": False}),
    ("⧉-004 ⧉-node-008-image",           {"read_only": False}),
    ("⫷-005 ⫷-node-009-wnn",             {"read_only": True}),
    ("〄-006 〄-node-010-user-trash",     {"read_only": False}),
    ("admin-dashboard",                   {"read_only": False, "admin_only": True, "key": "admin"}),
    ("∴ User Analytics ∴",               {"read_only": True,  "admin_only": True}),
]

ARCHIVE_CATEGORY_NAME = "⊡-the-archive"
ARCHIVE_DUMMY_CHANNEL = "⊡-the-archive"

SIGNED_ROLE_NAME = "Signed"

SQLITE_PATH = "data/wilhelmina.sqlite"
LANG_PATH   = "data/i18n/en-US.json"

# Entropy runes
RUNES = ["Ψ", "Ω", "Σ", "Δ", "✶", "⟡", "☿", "♇"]

# =========================
# ===== EMBED HELPERS =====
# =========================

def themed_embed(title: Optional[str] = None,
                 description: Optional[str] = None,
                 color: int = PRIMARY_HEX) -> discord.Embed:
    e = discord.Embed(title=title or discord.Embed.Empty,
                      description=description or discord.Embed.Empty,
                      color=color)
    e.set_footer(text=FOOTER_TEXT)
    return e

def glitch_header(text: str) -> str:
    return f"```ansi\n>> {text}\n```"

def code_line(text: str) -> str:
    return f"```\n{text}\n```"

# =========================
# ========= DB =============
# =========================

class DB:
    def __init__(self, path: str = SQLITE_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self._conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            signed_role_id INTEGER,
            circle_channel_id INTEGER,
            admin_log_channel_id INTEGER,
            tz TEXT,
            created_at TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            guild_id INTEGER,
            user_id INTEGER,
            chosen_name TEXT,
            birthdate TEXT,
            signed_at TEXT,
            soul_id TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            actor_id INTEGER,
            kind TEXT,
            detail_json TEXT,
            ts TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS serial_counter (
            guild_id INTEGER PRIMARY KEY,
            next_serial INTEGER
        )
        """)
        self._conn.commit()

    # ---- guild config
    def upsert_guild_config(self, guild_id: int, **kwargs):
        cfg = self.get_guild_config(guild_id) or {}
        cfg.update(kwargs)
        tz = cfg.get("tz") or TZ_DEFAULT
        created_at = cfg.get("created_at") or dt.datetime.utcnow().isoformat()
        cur = self._conn.cursor()
        cur.execute("""
        INSERT INTO guild_config(guild_id, signed_role_id, circle_channel_id, admin_log_channel_id, tz, created_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(guild_id) DO UPDATE SET
            signed_role_id=excluded.signed_role_id,
            circle_channel_id=excluded.circle_channel_id,
            admin_log_channel_id=excluded.admin_log_channel_id,
            tz=excluded.tz
        """, (guild_id, cfg.get("signed_role_id"), cfg.get("circle_channel_id"),
              cfg.get("admin_log_channel_id"), tz, created_at))
        self._conn.commit()

    def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM guild_config WHERE guild_id=?", (guild_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ---- members
    def get_member(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM members WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        row = cur.fetchone()
        return dict(row) if row else None

    def upsert_member(self, guild_id: int, user_id: int, **kwargs):
        existing = self.get_member(guild_id, user_id) or {}
        existing.update(kwargs)
        cur = self._conn.cursor()
        cur.execute("""
        INSERT INTO members(guild_id, user_id, chosen_name, birthdate, signed_at, soul_id)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            chosen_name=excluded.chosen_name,
            birthdate=excluded.birthdate,
            signed_at=excluded.signed_at,
            soul_id=excluded.soul_id
        """, (guild_id, user_id, existing.get("chosen_name"), existing.get("birthdate"),
              existing.get("signed_at"), existing.get("soul_id")))
        self._conn.commit()

    def list_members(self, guild_id: int):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM members WHERE guild_id=? ORDER BY signed_at ASC", (guild_id,))
        return [dict(r) for r in cur.fetchall()]

    # ---- events
    def log_event(self, guild_id: int, actor_id: Optional[int], kind: str, detail: Dict[str, Any]):
        cur = self._conn.cursor()
        cur.execute("INSERT INTO events(guild_id, actor_id, kind, detail_json, ts) VALUES (?,?,?,?,?)",
                    (guild_id, actor_id, kind, json.dumps(detail, ensure_ascii=False),
                     dt.datetime.utcnow().isoformat()))
        self._conn.commit()

    def list_events(self, guild_id: int):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM events WHERE guild_id=? ORDER BY id ASC", (guild_id,))
        return [dict(r) for r in cur.fetchall()]

    def prune_ritual_state(self, guild_id: int):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM events WHERE guild_id=? AND kind='ritual_state'", (guild_id,))
        self._conn.commit()

    # ---- serials
    def get_and_inc_serial(self, guild_id: int) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT next_serial FROM serial_counter WHERE guild_id=?", (guild_id,))
        row = cur.fetchone()
        if row is None:
            next_serial = 1
            cur.execute("INSERT INTO serial_counter(guild_id, next_serial) VALUES (?,?)",
                        (guild_id, 2))
        else:
            next_serial = row["next_serial"]
            inc = next_serial + 1
            if inc > 9999:
                inc = 1
            cur.execute("UPDATE serial_counter SET next_serial=? WHERE guild_id=?",
                        (inc, guild_id))
        self._conn.commit()
        return next_serial

# =========================
# ===== LANG PACK =========
# =========================

DEFAULT_LANG = {
    "ritual": {
        "start": ">> INITIALIZING // SUMMONING_CIRCLE",
        "beat_lines": [
            ">>> LINK OPENED : SIGNAL: {signal}",
            "[WARN] interference detected; patching…",
            "ACCESS OVERRIDE // @everyone — EYES FRONT.",
            "error: {code} // retrying…"
        ],
        "finale": ">>> CONTRACT REQUIRED // BEGIN SIGNING"
    },
    "contract": {
        "prompt_name": "Enter your chosen name.",
        "prompt_birthdate": "Birth date (YYYY-MM-DD).",
        "decline": {"rude": ["No signature? Then no access. Move along."]},
        "signed_dm": "Seal granted. Your Soul ID: {soul_id}",
        "signed_public": "Seal granted for <@{user_id}>."
    },
    "admin": {
        "init_preview_title": "Server Takeover Preview",
        "abort": "Ritual severed. Pending beats purged; lockdown persists."
    }
}

def load_lang() -> Dict[str, Any]:
    try:
        with open(LANG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_LANG

# =========================
# ===== UTILITIES =========
# =========================

def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator

def to_rtz(ts: dt.datetime, tz_name: str) -> dt.datetime:
    tz = ZoneInfo(tz_name)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(tz)

def name_glyph(chosen_name: str) -> str:
    letters = re.findall(r"[A-Za-z]", chosen_name or "")
    glyph = "".join(letters)[:2].upper()
    return glyph.ljust(2, "X")

def mint_soul_id(chosen_name: str, when: dt.datetime) -> str:
    glyph = name_glyph(chosen_name)
    yy = f"{when.year % 100:02d}"
    random.seed(int(when.timestamp()))
    rune = random.choice(RUNES)
    digit = random.randint(0, 9)
    serial = "0000"
    sigil = f"{glyph}{yy}{rune}{digit}"
    return f"⛧WLMN-{serial}-{sigil}⛧"

def with_serial(soul_id: str, serial: int) -> str:
    return soul_id.replace("0000", f"{serial:04d}", 1)

def chunk(seq: List[Any], n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

# ======================================
# ===== CONTRACT VIEWS / MODALS ========
# ======================================

class ContractModal(discord.ui.Modal, title="Soul Contract"):
    chosen_name = discord.ui.TextInput(label="Chosen Name", placeholder="Enter your chosen name", required=True, max_length=64)
    birthdate = discord.ui.TextInput(label="Birthdate (YYYY-MM-DD)", placeholder="YYYY-MM-DD", required=True, max_length=10)

    def __init__(self, cog: "Onboarding", member: discord.Member):
        super().__init__()
        self.cog = cog
        self.member = member
        self.lang = cog.lang

    async def on_submit(self, interaction: discord.Interaction):
        try:
            dt.date.fromisoformat(str(self.birthdate))
        except ValueError:
            await interaction.response.send_message(
                embed=themed_embed("Invalid date", f"{DIVIDER}\nPlease use `YYYY-MM-DD`.\n{DIVIDER}", color=discord.Color.red().value),
                ephemeral=True
            )
            return
        guild = self.member.guild
        await self.cog.complete_contract(guild=guild, user=self.member,
                                         chosen_name=str(self.chosen_name),
                                         birthdate=str(self.birthdate),
                                         respond=interaction.response)

class ContractView(discord.ui.View):
    def __init__(self, cog: "Onboarding", member: discord.Member, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.member = member
        self.lang = cog.lang

    @discord.ui.button(label="Sign", style=discord.ButtonStyle.success)
    async def sign(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(embed=themed_embed("Not your contract.", "This seal is bound to another.",
                                                                       color=discord.Color.red().value), ephemeral=True)
            return
        await interaction.response.send_modal(ContractModal(self.cog, self.member))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(embed=themed_embed("Not your contract.", "This seal is bound to another.",
                                                                       color=discord.Color.red().value), ephemeral=True)
            return
        rude_lines = (self.lang.get("contract", {}).get("decline", {}) or {}).get("rude", []) or DEFAULT_LANG["contract"]["decline"]["rude"]
        text = random.choice(rude_lines)
        await interaction.response.send_message(embed=themed_embed("Declined", text))
        self.cog.db.log_event(self.member.guild.id, interaction.user.id, "contract_declined", {"user_id": interaction.user.id})
        await self.cog.log_admin(self.member.guild, "contract_declined", {"user_id": interaction.user.id})

# ======================================
# ===== RITUAL SCHEDULER ================
# ======================================

@dataclass
class RitualState:
    guild_id: int
    started_at: dt.datetime
    beats: List[float]
    next_index: int = 0
    everyone_count: int = 0
    member_mentions_done: int = 0
    last_everyone_ts: Optional[float] = None
    task: Optional[asyncio.Task] = None
    aborted: bool = False

class RitualQueue:
    def __init__(self, cog: "Onboarding"):
        self.cog = cog
        self.states: Dict[int, RitualState] = {}

    def active(self, guild_id: int) -> Optional[RitualState]:
        st = self.states.get(guild_id)
        if st and not st.aborted: return st
        return None

    async def start(self, guild: discord.Guild, circle: discord.TextChannel):
        if self.active(guild.id): raise RuntimeError("Ritual already active.")
        now = dt.datetime.utcnow()
        beats_count = 12
        base_gap = RITUAL_DURATION_S / (beats_count + 1)
        beats, acc = [], 0.0
        for _ in range(beats_count):
            jitter = random.uniform(*RITUAL_JITTER_RANGE)
            acc += base_gap + jitter
            beats.append(acc)
        beats.append(RITUAL_DURATION_S - random.uniform(*RITUAL_JITTER_RANGE))
        state = RitualState(guild_id=guild.id, started_at=now, beats=beats, next_index=0)
        self.states[guild.id] = state
        await self.cog.persist_ritual_state(guild.id, state)
        task = asyncio.create_task(self._runner(guild, circle, state))
        state.task = task
        self.cog.db.log_event(guild.id, None, "ritual_start", {"started_at": now.isoformat(), "beats": beats})
        await self.cog.log_admin(guild, "ritual_start", {"beats": beats})

    async def abort(self, guild: discord.Guild):
        st = self.states.get(guild.id)
        if not st: return False
        st.aborted = True
        if st.task and not st.task.done():
            st.task.cancel()
            try: await st.task
            except asyncio.CancelledError: pass
        self.cog.db.log_event(guild.id, None, "ritual_abort", {"ts": dt.datetime.utcnow().isoformat()})
        await self.cog.log_admin(guild, "ritual_abort", {})
        return True

    async def _runner(self, guild: discord.Guild, circle: discord.TextChannel, st: RitualState):
        lang = self.cog.lang
        lines  = (lang.get("ritual") or {}).get("beat_lines", DEFAULT_LANG["ritual"]["beat_lines"])
        finale = (lang.get("ritual") or {}).get("finale", DEFAULT_LANG["ritual"]["finale"])
        start_line = (lang.get("ritual") or {}).get("start", DEFAULT_LANG["ritual"]["start"])

        await circle.send(embed=themed_embed("Summoning", f"{DIVIDER}\n{start_line}\n{DIVIDER}"))
        t0 = st.started_at.timestamp()
        while st.next_index < len(st.beats) and not st.aborted:
            target = t0 + st.beats[st.next_index]
            now = dt.datetime.utcnow().timestamp()
            delay = max(0.0, target - now)
            try:    await asyncio.sleep(delay)
            except asyncio.CancelledError: return

            line = random.choice(lines).format(signal=random.randint(100, 999), code=random.randint(100, 599))
            content = None
            embed = themed_embed("Ritual Beat", f"{DIVIDER}\n{line}\n{DIVIDER}")

            # @everyone pacing
            if "@everyone" in line:
                can_everyone = st.everyone_count < EVERYONE_MAX_TOTAL
                now_ts = dt.datetime.utcnow().timestamp()
                gap_ok = (st.last_everyone_ts is None) or ((now_ts - st.last_everyone_ts) >= EVERYONE_MIN_GAP_S)
                if can_everyone and gap_ok:
                    content = "@everyone"
                    st.everyone_count += 1
                    st.last_everyone_ts = now_ts

            # per-member mentions
            mentions: List[str] = []
            if st.member_mentions_done < PER_RITUAL_MEMBER_MENTIONS_MAX:
                to_pick = min(PER_BEAT_MEMBER_MENTIONS, PER_RITUAL_MEMBER_MENTIONS_MAX - st.member_mentions_done)
                pool = [m for m in guild.members if not (m.bot or is_admin(m))]
                random.shuffle(pool)
                sample = pool[:to_pick]
                mentions = [m.mention for m in sample]
                st.member_mentions_done += len(mentions)
            if mentions:
                embed.description = f"{embed.description}\n" + "\n".join(mentions)

            try:
                await circle.send(content=content, embed=embed,
                                  allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
            except discord.HTTPException:
                pass

            st.next_index += 1
            await self.cog.persist_ritual_state(guild.id, st)

        if not st.aborted:
            await circle.send(embed=themed_embed("Finale", f"{DIVIDER}\n{finale}\n{DIVIDER}"))
            self.cog.db.log_event(guild.id, None, "ritual_end", {"ts": dt.datetime.utcnow().isoformat()})
            await self.cog.log_admin(guild, "ritual_end", {})
            self.cog.db.prune_ritual_state(guild.id)

        self.states.pop(guild.id, None)

# ======================================
# ===== MAIN COG =======================
# ======================================

class Onboarding(commands.Cog):
    """Wilhelmina Onboarding + Ritual + Contract"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DB(SQLITE_PATH)
        self.lang = load_lang()
        self.rituals = RitualQueue(self)
        self._resume_task = asyncio.create_task(self._maybe_resume_rituals())

    # -------- internal logging

    async def log_admin(self, guild: discord.Guild, kind: str, detail: Dict[str, Any]):
        admin_channel = discord.utils.get(guild.text_channels, name="admin-dashboard")
        if not admin_channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me.top_role: discord.PermissionOverwrite(view_channel=True)
            }
            admin_channel = await guild.create_text_channel("admin-dashboard", overwrites=overwrites, reason="Wilhelmina: admin log")

        human = f"[{kind}] {detail}"
        e = themed_embed("Audit", f"{DIVIDER}\n{human}\n{DIVIDER}", color=ACCENT_HEX)
        compact = json.dumps(detail, ensure_ascii=False)
        e.add_field(name="detail_json", value=f"```json\n{compact}\n```", inline=False)
        try:
            await admin_channel.send(embed=e)
        except discord.HTTPException:
            pass

    # -------- ritual persistence (via events)

    async def persist_ritual_state(self, guild_id: int, st: RitualState):
        detail = {
            "started_at": st.started_at.isoformat(),
            "beats": st.beats,
            "next_index": st.next_index,
            "everyone_count": st.everyone_count,
            "member_mentions_done": st.member_mentions_done,
            "last_everyone_ts": st.last_everyone_ts,
            "aborted": st.aborted
        }
        self.db.log_event(guild_id, None, "ritual_state", detail)

    async def _maybe_resume_rituals(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                events = list(reversed(self.db.list_events(guild.id)))
                last_state = next((e for e in events if e["kind"] == "ritual_state"), None)
                last_start = next((e for e in events if e["kind"] == "ritual_start"), None)
                ended_or_aborted = next((e for e in events if e["kind"] in ("ritual_end", "ritual_abort")), None)

                if last_start and not ended_or_aborted:
                    started_at = dt.datetime.fromisoformat(last_start["detail_json"] and json.loads(last_start["detail_json"])["started_at"])
                    if (dt.datetime.utcnow() - started_at).total_seconds() <= RESUME_WINDOW_S:
                        state_json = json.loads(last_state["detail_json"]) if last_state else None
                        if state_json:
                            st = RitualState(
                                guild_id=guild.id,
                                started_at=dt.datetime.fromisoformat(state_json["started_at"]),
                                beats=state_json["beats"],
                                next_index=state_json["next_index"],
                                everyone_count=state_json["everyone_count"],
                                member_mentions_done=state_json["member_mentions_done"],
                                last_everyone_ts=state_json["last_everyone_ts"],
                                aborted=False
                            )
                            circle = await self._get_or_create_circle(guild)
                            task = asyncio.create_task(self.rituals._runner(guild, circle, st))
                            st.task = task
                            self.rituals.states[guild.id] = st
                            await self.log_admin(guild, "ritual_resume", {"next_index": st.next_index})
            except Exception:
                continue

    # -------- permissions & channels scaffold

    async def _get_or_create_signed_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name=SIGNED_ROLE_NAME)
        if role: return role
        role = await guild.create_role(name=SIGNED_ROLE_NAME, colour=discord.Colour(PRIMARY_HEX), reason="Wilhelmina: Signed role")
        try:
            await role.edit(position=min(guild.me.top_role.position - 1, len(guild.roles)-1))
        except discord.HTTPException:
            await self.log_admin(guild, "role_position_warning", {"message": "Could not place 'Signed' role above @everyone. Check bot role hierarchy."})
        else:
            if role.position <= guild.default_role.position:
                await self.log_admin(guild, "role_position_warning", {"message": "'Signed' role not above @everyone. Adjust roles."})
        return role

    async def _get_or_create_circle(self, guild: discord.Guild) -> discord.TextChannel:
        ch = discord.utils.get(guild.text_channels, name="⛧-000 ⛧-summoning-circle")
        if ch: return ch
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            guild.me.top_role:  discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True, create_public_threads=True, create_private_threads=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True, create_public_threads=True, create_private_threads=True),
        }
        ch = await guild.create_text_channel("⛧-000 ⛧-summoning-circle", overwrites=overwrites, reason="Wilhelmina: summoning circle")
        return ch

    async def _ensure_layout(self, guild: discord.Guild) -> Tuple[discord.TextChannel, discord.TextChannel, discord.Role]:
        archive_cat = discord.utils.get(guild.categories, name=ARCHIVE_CATEGORY_NAME)
        if not archive_cat:
            archive_cat = await guild.create_category(ARCHIVE_CATEGORY_NAME, reason="Wilhelmina: archive")
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me.top_role:  discord.PermissionOverwrite(view_channel=True)
            }
            await guild.create_text_channel(ARCHIVE_DUMMY_CHANNEL, category=archive_cat, overwrites=overwrites)

        signed = await self._get_or_create_signed_role(guild)
        circle, admin_ch = None, None

        for name, meta in CHANNELS_ORDERED:
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch:
                if meta.get("key") == "circle": circle = ch
                if meta.get("key") == "admin":  admin_ch = ch
                continue
            overwrites = {}
            if name == "⛧-000 ⛧-summoning-circle":
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            else:
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False, send_messages=False)
            if meta.get("read_only"):
                overwrites[signed] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            else:
                overwrites[signed] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            if meta.get("admin_only"):
                overwrites[signed] = discord.PermissionOverwrite(view_channel=False)
                overwrites[guild.me.top_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_webhooks=True)
            ch = await guild.create_text_channel(name, overwrites=overwrites, reason="Wilhelmina: layout")
            if meta.get("key") == "circle": circle = ch
            if meta.get("key") == "admin":  admin_ch = ch

        # Move everything old (text/voice/forum/media) to Archive
        our_names = {n for n, _ in CHANNELS_ORDERED}
        for ch in guild.text_channels:
            if ch.category and ch.category.id == archive_cat.id: continue
            if ch.name in our_names: continue
            try: await ch.edit(category=archive_cat, reason="Wilhelmina: archive (text)")
            except discord.HTTPException: pass
        for ch in guild.voice_channels:
            if ch.category and ch.category.id == archive_cat.id: continue
            try: await ch.edit(category=archive_cat, reason="Wilhelmina: archive (voice)")
            except discord.HTTPException: pass
        for ch in getattr(guild, "forums", []):
            if ch.category and ch.category.id == archive_cat.id: continue
            try: await ch.edit(category=archive_cat, reason="Wilhelmina: archive (forum)")
            except Exception: pass
        for ch in getattr(guild, "media_channels", []):
            if ch.category and ch.category.id == archive_cat.id: continue
            try: await ch.edit(category=archive_cat, reason="Wilhelmina: archive (media)")
            except Exception: pass
        for cat in guild.categories:
            if cat.id == archive_cat.id: continue
            if not cat.channels:
                try: await cat.delete(reason="Wilhelmina: removed empty category after archive")
                except discord.HTTPException: pass

        circle = circle or await self._get_or_create_circle(guild)
        admin_ch = admin_ch or discord.utils.get(guild.text_channels, name="admin-dashboard")
        self.db.upsert_guild_config(guild.id, signed_role_id=signed.id, circle_channel_id=circle.id,
                                    admin_log_channel_id=admin_ch.id if admin_ch else None, tz=TZ_DEFAULT)
        return circle, admin_ch, signed

    # -------- contract workflow

    async def send_contract(self, member: discord.Member):
        lang = self.lang
        e = themed_embed("Soul Contract", f"{DIVIDER}\n{lang['contract']['prompt_name']}\n{lang['contract']['prompt_birthdate']}\n{DIVIDER}")
        view = ContractView(self, member)

        try:
            dm = await member.create_dm()
            await dm.send(embed=e, view=view)
            self.db.log_event(member.guild.id, member.id, "contract_sent", {"via": "dm"})
            await self.log_admin(member.guild, "contract_sent", {"user_id": member.id, "via": "dm"})
            return
        except discord.Forbidden:
            pass

        circle = await self._get_or_create_circle(member.guild)
        try:
            th = await circle.create_thread(name=f"seal-{member.name}-{member.id}",
                                            type=discord.ChannelType.private_thread, invitable=False)
            await th.add_user(member)
            await th.send(embed=e, view=view)
            self.db.log_event(member.guild.id, member.id, "contract_sent", {"via": "private_thread", "thread_id": th.id})
            await self.log_admin(member.guild, "contract_sent", {"user_id": member.id, "via": "private_thread", "thread_id": th.id})
        except discord.HTTPException:
            try:
                temp_cat = discord.utils.get(member.guild.categories, name="⛧-temp-seal")
                if not temp_cat:
                    temp_cat = await member.guild.create_category(
                        "⛧-temp-seal", reason="Wilhelmina: contract fallback",
                        overwrites={
                            member.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            member.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
                        })
                overwrites = {
                    member.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    member.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
                }
                chan = await member.guild.create_text_channel(f"seal-{member.id}", category=temp_cat, overwrites=overwrites)
                await chan.send(content=member.mention, embed=e, view=view)
                self.db.log_event(member.guild.id, member.id, "contract_sent", {"via": "temp_channel", "channel_id": chan.id})
                await self.log_admin(member.guild, "contract_sent", {"user_id": member.id, "via": "temp_channel", "channel_id": chan.id})
            except Exception:
                await circle.send(content=member.mention, embed=e)
                self.db.log_event(member.guild.id, member.id, "contract_sent", {"via": "circle"})
                await self.log_admin(member.guild, "contract_sent", {"user_id": member.id, "via": "circle"})

    async def complete_contract(self, guild: discord.Guild, user: discord.Member, chosen_name: str, birthdate: str,
                                respond: discord.InteractionResponse):
        role = await self._get_or_create_signed_role(guild)
        try:
            await user.add_roles(role, reason="Wilhelmina: contract signed")
        except discord.HTTPException:
            pass

        now = dt.datetime.utcnow()
        sid = mint_soul_id(chosen_name, now)
        serial = self.db.get_and_inc_serial(guild.id)
        sid = with_serial(sid, serial)

        self.db.upsert_member(guild.id, user.id, chosen_name=chosen_name, birthdate=birthdate,
                              signed_at=now.isoformat(), soul_id=sid)

        lang = self.lang
        dm_text = (lang["contract"].get("signed_dm") or DEFAULT_LANG["contract"]["signed_dm"]).format(soul_id=sid)
        await respond.send_message(embed=themed_embed("Seal Granted", dm_text, color=ACCENT2_HEX), ephemeral=True)

        pub_text = (lang["contract"].get("signed_public") or DEFAULT_LANG["contract"]["signed_public"]).format(user_id=user.id)
        circle = await self._get_or_create_circle(guild)
        await circle.send(embed=themed_embed("Seal Granted", f"{DIVIDER}\n{pub_text}\n{DIVIDER}", color=ACCENT2_HEX))

        self.db.log_event(guild.id, user.id, "contract_signed", {"user_id": user.id, "soul_id": sid})
        await self.log_admin(guild, "contract_signed", {"user_id": user.id, "soul_id": sid})

        # Cleanup temp private channel if used
        try:
            temp_cat = discord.utils.get(guild.categories, name="⛧-temp-seal")
            if temp_cat:
                for ch in list(temp_cat.channels):
                    if ch.name == f"seal-{user.id}":
                        await ch.delete(reason="Wilhelmina: contract complete cleanup")
                if not temp_cat.channels:
                    await temp_cat.delete(reason="Wilhelmina: cleanup empty temp-seal category")
        except Exception:
            pass

    # -------- listeners

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if is_admin(member):
            try:
                await member.send(embed=themed_embed("Bypass", "You are exempt by Discord law; the gate is ceremonial for you."))
            except discord.Forbidden:
                pass
            self.db.log_event(member.guild.id, member.id, "admin_bypass", {})
            await self.log_admin(member.guild, "admin_bypass", {"user_id": member.id})
            return
        await self.send_contract(member)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Delete any interruptions in the circle during ritual (bots included), but not Wilhelmina
        if message.author.id == self.bot.user.id:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        st = self.rituals.active(message.guild.id)
        if not st:
            return
        cfg = self.db.get_guild_config(message.guild.id)
        circle_id = cfg and cfg.get("circle_channel_id")
        if circle_id and message.channel.id == circle_id:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            self.db.log_event(message.guild.id, message.author.id, "circle_interruption_deleted", {"message_id": message.id})
            await self.log_admin(message.guild, "circle_interruption_deleted", {"user_id": message.author.id, "message_id": message.id})

    # -------- commands

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="init-server", description="Preview & confirm Wilhelmina server takeover.")
    async def init_server(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return

        current_names = {c.name for c in guild.text_channels}
        to_create = [n for n, _ in CHANNELS_ORDERED if n not in current_names]
        our_names = {n for n, _ in CHANNELS_ORDERED}
        to_archive = [c.name for c in guild.text_channels if c.name not in our_names]

        lang = self.lang
        e = themed_embed(lang["admin"].get("init_preview_title", "Server Takeover Preview"),
                         f"{DIVIDER}\n**Create:**\n- " + "\n- ".join(to_create or ["(none)"]) +
                         f"\n\n**Archive:**\n- " + "\n- ".join(to_archive or ["(none)"]) + f"\n{DIVIDER}")
        view = ConfirmInitView(self)
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="ritual-start", description="Begin the 13-minute summoning ritual.")
    async def ritual_start(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return
        circle, _, _ = await self._ensure_layout(guild)

        # Preflight: ensure we can moderate & ping @everyone
        me: discord.Member = guild.me
        perms = circle.permissions_for(me)
        missing = []
        if not perms.manage_messages: missing.append("Manage Messages in summoning-circle")
        if not perms.send_messages:   missing.append("Send Messages in summoning-circle")
        if not guild.me.guild_permissions.mention_everyone: missing.append("Mention @everyone (server-level)")
        if missing:
            checklist = "\n- ".join(missing)
            await interaction.response.send_message(
                embed=themed_embed(
                    "Ritual Preflight Failed",
                    f"{DIVIDER}\nGrant the following and retry:\n- {checklist}\n{DIVIDER}",
                    color=discord.Color.red().value
                ),
                ephemeral=True
            )
            await self.log_admin(guild, "preflight_failed", {"missing": missing})
            return

        try:
            await self.rituals.start(guild, circle)
        except RuntimeError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.send_message(embed=themed_embed("Ritual", "Summoning initialized."), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="ritual-status", description="Show ritual status and next 3 beats.")
    async def ritual_status(self, interaction: discord.Interaction):
        st = self.rituals.active(interaction.guild.id) if interaction.guild else None
        if not st:
            await interaction.response.send_message(embed=themed_embed("Ritual", "No active ritual."), ephemeral=True)
            return
        next_idxs = list(range(st.next_index, min(st.next_index + 3, len(st.beats))))
        now = dt.datetime.utcnow().timestamp()
        t0 = st.started_at.timestamp()
        lines = []
        for i in next_idxs:
            eta = max(0, int(t0 + st.beats[i] - now))
            lines.append(f"Beat {i+1} in ~{eta}s")
        desc = f"{DIVIDER}\nStarted: {st.started_at.isoformat()}\n" \
               f"Everyone used: {st.everyone_count}/{EVERYONE_MAX_TOTAL}\n" \
               f"Member mentions: {st.member_mentions_done}/{PER_RITUAL_MEMBER_MENTIONS_MAX}\n" \
               f"Next:\n- " + "\n- ".join(lines or ["(none)"]) + f"\n{DIVIDER}"
        await interaction.response.send_message(embed=themed_embed("Ritual Status", desc), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="ritual-abort", description="Abort ritual: purge queued beats, keep lockdown.")
    async def ritual_abort(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return
        ok = await self.rituals.abort(guild)
        msg = self.lang["admin"].get("abort", DEFAULT_LANG["admin"]["abort"])
        circle = await self._get_or_create_circle(guild)
        if ok:
            await circle.send(embed=themed_embed("Ritual Severed", f"{DIVIDER}\n{msg}\n{DIVIDER}", color=discord.Color.red().value))
            await interaction.response.send_message(embed=themed_embed("Ritual", "Aborted."), ephemeral=True)
            # Prune ritual_state snapshots to avoid growth
            self.db.prune_ritual_state(guild.id)
        else:
            await interaction.response.send_message(embed=themed_embed("Ritual", "No active ritual."), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="User to resend contract to")
    @app_commands.command(name="resend-contract", description="Resend the soul contract to a user.")
    async def resend_contract(self, interaction: discord.Interaction, user: discord.Member):
        await self.send_contract(user)
        await interaction.response.send_message(embed=themed_embed("Contract", "Resent."), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="User to revoke", reason="Optional reason")
    @app_commands.command(name="revoke-contract", description="Revoke a user's signed status and invalidate their ID.")
    async def revoke_contract(self, interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = None):
        guild = interaction.guild
        role = await self._get_or_create_signed_role(guild)
        try:
            await user.remove_roles(role, reason=reason or "Wilhelmina: revoke")
        except discord.HTTPException:
            pass
        self.db.upsert_member(guild.id, user.id, soul_id=None)
        self.db.log_event(guild.id, interaction.user.id, "contract_revoked", {"user_id": user.id, "reason": reason})
        await self.log_admin(guild, "contract_revoked", {"user_id": user.id, "reason": reason})
        await interaction.response.send_message(embed=themed_embed("Contract", "Revoked."), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(format="csv or json", include_audit="Include audit events")
    @app_commands.choices(format=[app_commands.Choice(name="csv", value="csv"),
                                  app_commands.Choice(name="json", value="json")])
    @app_commands.command(name="export-records", description="Export member records (and optionally audit events).")
    async def export_records(self, interaction: discord.Interaction,
                             format: app_commands.Choice[str],
                             include_audit: Optional[bool] = False):
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)
        fmt = format.value
        members = self.db.list_members(guild.id)

        if fmt == "json":
            payload = {"members": members}
            if include_audit:
                payload["events"] = self.db.list_events(guild.id)
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            fp = io.BytesIO(data); fp.seek(0)
            await interaction.followup.send(content="Export ready.", file=discord.File(fp, filename="wilhelmina_export.json"), ephemeral=True)
        else:
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=["guild_id","user_id","chosen_name","birthdate","signed_at","soul_id"])
            writer.writeheader()
            for m in members: writer.writerow(m)
            files = [discord.File(io.BytesIO(out.getvalue().encode("utf-8")), filename="members.csv")]
            if include_audit:
                events = self.db.list_events(guild.id)
                out2 = io.StringIO()
                ew = csv.DictWriter(out2, fieldnames=["id","guild_id","actor_id","kind","detail_json","ts"])
                ew.writeheader()
                for e in events: ew.writerow(e)
                files.append(discord.File(io.BytesIO(out2.getvalue().encode("utf-8")), filename="events.csv"))
            await interaction.followup.send(content="Export ready.", files=files, ephemeral=True)

# ============= INIT CONFIRM VIEW ==============

class ConfirmInitView(discord.ui.View):
    def __init__(self, cog: Onboarding, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.cog = cog

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        circle, admin_ch, signed = await self.cog._ensure_layout(guild)
        e = themed_embed("Takeover Complete", f"{DIVIDER}\nChannels created, archive ready, gate enforced.\n{DIVIDER}", color=ACCENT2_HEX)
        await interaction.followup.send(embed=e, ephemeral=True)
        self.cog.db.log_event(guild.id, interaction.user.id, "init_complete", {"circle_id": circle.id, "signed_role_id": signed.id})
        await self.cog.log_admin(guild, "init_complete", {"circle_id": circle.id, "signed_role_id": signed.id})

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=themed_embed("Cancelled", "No changes applied."), ephemeral=True)
        self.stop()

# ============= EXTENSION SETUP =================

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))