import unittest
from unittest import mock

from config import settings as settings_module


class SettingsTests(unittest.TestCase):
    def load_with_env(self, values):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict("os.environ", values, clear=True):
                return settings_module.load_settings()

    def test_missing_discord_token_raises(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict("os.environ", {"COMMAND_SYNC_MODE": "off"}, clear=True):
                with self.assertRaisesRegex(settings_module.SettingsError, "DISCORD_TOKEN"):
                    settings_module.load_settings()

    def test_guild_sync_requires_home_guild_id(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict(
                "os.environ",
                {"DISCORD_TOKEN": "token", "COMMAND_SYNC_MODE": "guild"},
                clear=True,
            ):
                with self.assertRaisesRegex(settings_module.SettingsError, "HOME_GUILD_ID"):
                    settings_module.load_settings()

    def test_dedicated_server_settings_load(self):
        loaded = self.load_with_env(
            {
                "DISCORD_TOKEN": "token",
                "HOME_GUILD_ID": "12345",
                "COMMAND_SYNC_MODE": "guild",
            }
        )

        self.assertEqual(loaded.server_mode, "dedicated")
        self.assertEqual(loaded.home_guild_id, 12345)
        self.assertEqual(loaded.command_sync_mode, "guild")

    def test_legacy_dev_guild_id_alias_sets_home_guild(self):
        loaded = self.load_with_env(
            {
                "DISCORD_TOKEN": "token",
                "DEV_GUILD_ID": "67890",
                "COMMAND_SYNC_MODE": "dev",
            }
        )

        self.assertEqual(loaded.home_guild_id, 67890)
        self.assertEqual(loaded.command_sync_mode, "guild")

    def test_server_takeover_mode_is_rejected(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict(
                "os.environ",
                {
                    "DISCORD_TOKEN": "token",
                    "COMMAND_SYNC_MODE": "off",
                    "SERVER_MODE": "takeover",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(settings_module.SettingsError, "dedicated"):
                    settings_module.load_settings()

    def test_feature_flags_parse(self):
        loaded = self.load_with_env(
            {
                "DISCORD_TOKEN": "token",
                "COMMAND_SYNC_MODE": "off",
                "ENABLE_CORE": "true",
                "ENABLE_ADMIN": "true",
                "ENABLE_INVITE": "1",
                "ENABLE_ORACLES": "false",
            }
        )

        self.assertTrue(loaded.is_cog_enabled("cogs.core"))
        self.assertTrue(loaded.is_cog_enabled("cogs.admin"))
        self.assertTrue(loaded.is_cog_enabled("cogs.invite"))
        self.assertFalse(loaded.is_cog_enabled("cogs.oracles"))

    def test_required_admin_cannot_be_disabled(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict(
                "os.environ",
                {
                    "DISCORD_TOKEN": "token",
                    "COMMAND_SYNC_MODE": "off",
                    "ENABLE_CORE": "true",
                    "ENABLE_ADMIN": "false",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(settings_module.SettingsError, "ENABLE_ADMIN"):
                    settings_module.load_settings()


if __name__ == "__main__":
    unittest.main()
