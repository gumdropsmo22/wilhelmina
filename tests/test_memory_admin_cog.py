from __future__ import annotations

import unittest
from types import SimpleNamespace

from cogs.memory_admin import (
    DISCORD_EMBED_TEXT_LIMIT,
    MAX_DISCORD_USER_ID,
    RECEIPT_MESSAGE_TEXT_BUDGET,
    MemoryAdmin,
    _embed_text_size,
    _parse_user_id,
    _receipt_embed_groups,
    _send_receipt_embed_groups,
)
from services import memory_ledger


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))

    def is_done(self):
        return bool(self.messages)


class DummyFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class DummyInteraction:
    def __init__(self, *, guild_id: int, administrator: bool):
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=55,
            guild_permissions=SimpleNamespace(administrator=administrator),
        )
        self.response = DummyResponse()
        self.followup = DummyFollowup()


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


class ReceiptEmbedBudgetTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _receipt(receipt_id: int) -> memory_ledger.MemoryReceipt:
        message_id = 900000000000000000 + receipt_id
        return memory_ledger.MemoryReceipt(
            id=receipt_id,
            memory_id=77,
            guild_id=100,
            source_kind="discord",
            source_context="guild",
            author_user_id=800000000000000000 + receipt_id,
            channel_id=700000000000000000,
            message_id=message_id,
            jump_url=(
                "https://discord.com/channels/100/700000000000000000/"
                f"{message_id}"
            ),
            original_excerpt="O" * 5000,
            edited_excerpt="E" * 5000,
            source_created_at="2026-08-12T12:00:00+00:00",
            source_edited_at="2026-08-12T12:05:00+00:00",
            source_deleted_at=None,
            created_at="2026-08-12T12:00:01+00:00",
        )

    async def test_long_receipt_page_splits_into_safe_ephemeral_messages(self):
        receipts = [self._receipt(receipt_id) for receipt_id in range(1, 9)]

        groups = _receipt_embed_groups(
            receipts,
            current_page=1,
            page_count=1,
            total_receipts=8,
        )

        self.assertGreater(len(groups), 1)
        self.assertEqual(
            [embed.title for group in groups for embed in group],
            [f"Receipt #{receipt_id} · memory #77" for receipt_id in range(1, 9)],
        )
        for part_number, group in enumerate(groups, start=1):
            self.assertLessEqual(
                sum(_embed_text_size(embed) for embed in group),
                RECEIPT_MESSAGE_TEXT_BUDGET,
            )
            for embed in group:
                self.assertLessEqual(_embed_text_size(embed), DISCORD_EMBED_TEXT_LIMIT)
            footer = group[-1].footer.text or ""
            self.assertIn("Page 1/1", footer)
            self.assertIn(f"part {part_number}/{len(groups)}", footer)
            self.assertIn("/8", footer)

        interaction = DummyInteraction(guild_id=100, administrator=True)
        await _send_receipt_embed_groups(interaction, groups)

        self.assertEqual(len(interaction.response.messages), 1)
        self.assertEqual(len(interaction.followup.messages), len(groups) - 1)
        self.assertIs(interaction.response.messages[0][1]["embeds"], groups[0])
        self.assertTrue(interaction.response.messages[0][1]["ephemeral"])
        for index, (_, kwargs) in enumerate(interaction.followup.messages, start=1):
            self.assertIs(kwargs["embeds"], groups[index])
            self.assertTrue(kwargs["ephemeral"])


if __name__ == "__main__":
    unittest.main()