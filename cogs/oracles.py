from __future__ import annotations
import random
from discord.ext import commands
import discord
from utils.embeds import build_embed
from utils.persona import say
import json
from pathlib import Path

DATA_DIR = Path("data")

def _load_json(name: str):
    p = DATA_DIR / name
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

ROLL_LORE = _load_json("roll_lore.json")
FORTUNES = _load_json("fortunes.json")

class Oracles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="roll", description="Rolls a divination die.")
    async def roll(self, ctx: commands.Context, sides: int = 20):
        sides = max(2, min(1000, sides))
        result = random.randint(1, sides)
        lore = ROLL_LORE.get(str(result)) or _lore_for_number(result)
        emb = build_embed(title="▒▒ DIVINATION: ROLL ▒▒", description=f"**{result}**\n{lore}")
        await ctx.reply(embed=emb, mention_author=False)

    @commands.hybrid_command(name="fortune", description="One eerie fortune line.")
    async def fortune(self, ctx: commands.Context):
        line = random.choice(FORTUNES)
        emb = build_embed(title="▒▒ FORTUNE ▒▒", description=line)
        await ctx.reply(embed=emb, mention_author=False)

    @commands.hybrid_command(name="eightball", description="Mystic 8-ball.")
    async def eightball(self, ctx: commands.Context):
        # Weighted categories per spec: Yes 33%, No 33%, Maybe 17%, Ask Again 17%.
        pick = random.choices(
            population=["yes","no","maybe","again"],
            weights=[33,33,17,17],
            k=1
        )[0]
        options = {
            "yes": [say("Signs say yes."), say("The mirror nods.")],
            "no": [say("No, the veil refuses."), say("Not tonight.")],
            "maybe": [say("The smoke swirls… maybe."), say("Unclear omens.")],
            "again": [say("Ask again, witchling."), say("The cards hiss—retry.")],
        }
        emb = build_embed(title="▒▒ ORACLE: 8-BALL ▒▒", description=random.choice(options[pick]))
        await ctx.reply(embed=emb, mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Oracles(bot))

def _lore_for_number(n: int) -> str:
    if n in (13, 66, 77, 111, 333):
        return say("An omen trembles through the wires.")
    if _is_prime(n):
        return say("Indivisible. Alone. Resonant.")
    if n % 2 == 0:
        return say("Dull symmetry hums.")
    return say("Odd chaos stirs.")

def _is_prime(n: int) -> bool:
    if n < 2: return False
    if n % 2 == 0: return n == 2
    f = 3
    while f * f <= n:
        if n % f == 0: return False
        f += 2
    return True
