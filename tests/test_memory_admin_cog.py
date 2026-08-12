from __future__ import annotations

import unittest
from types import SimpleNamespace

from cogs.memory_admin import MAX_DISCORD_USER_ID, MemoryAdmin, _parse_user_id


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))

    def is_done(self):
        return bool(self.messages)


class DummyInteraction:
    def __init__(self, *, guild_id: int, administrator: bool):
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=55,
            guild_permissions=SimpleNamespace(administrator=administrator),
        )
        self.response = DummyResponse()
        self.followup = SimpleNamespace()


class DummyBot:
    def __init__(self):
        self.settings = SimpleNamespace(home_guild_id=100, database_path="unused.sqlite3")


class MemoryAdminAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_is_denied_ephemerally(self):
        cog = MemoryAdmin(DummyBot())
        interaction = DummyInteraction(guild_id=100, administrator=False)

        guild_id = await cog._guard(interaction)

        self.assertIsNone(guild_id)
        self.assertEqual(interaction.response.messages[0][0], "Admins only.")
        self.assertTrue(interaction.response.messages[0][1]["ephemeral"])

    async def test_admin_outside_home_guild_is_denied_ephemerally(self):
        cog = MemoryAdmin(DummyBot())
        interaction = DummyInteraction(guild_id=101, administrator=True)

        guild_id = await cog._guard(interaction)

        self.assertIsNone(guild_id)
        self.assertIn("configured home guild", interaction.response.messages[0][0])
        self.assertTrue(interaction.response.messages[0][1]["ephemeral"])

    async def test_admin_in_home_guild_is_authorized_without_response(self):
        cog = MemoryAdmin(DummyBot())
        interaction = DummyInteraction(guild_id=100, administrator=True)

        guild_id = await cog._guard(interaction)

        self.assertEqual(guild_id, 100)
        self.assertEqual(interaction.response.messages, [])


class ArchivedMemberIdTests(unittest.TestCase):
    def test_accepts_positive_discord_snowflake_string(self):
        self.assertEqual(_parse_user_id("123456789012345678"), 123456789012345678)

    def test_accepts_whitespace_around_valid_id(self):
        self.assertEqual(_parse_user_id("  42  "), 42)

    def test_rejects_non_decimal_ids(self):
        for value in ("", "-1", "+1", "1.5", "abc", "<@123>"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_user_id(value)

    def test_rejects_zero_and_ids_above_64_bit_range(self):
        with self.assertRaises(ValueError):
            _parse_user_id("0")
        with self.assertRaises(ValueError):
            _parse_user_id(str(MAX_DISCORD_USER_ID + 1))

    def test_accepts_maximum_64_bit_value(self):
        self.assertEqual(_parse_user_id(str(MAX_DISCORD_USER_ID)), MAX_DISCORD_USER_ID)


if __name__ == "__main__":
    unittest.main()
