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

    def test_dev_sync_requires_guild_id(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict(
                "os.environ",
                {"DISCORD_TOKEN": "token", "COMMAND_SYNC_MODE": "dev"},
                clear=True,
            ):
                with self.assertRaisesRegex(settings_module.SettingsError, "DEV_GUILD_ID"):
                    settings_module.load_settings()

    def test_feature_flags_parse(self):
        loaded = self.load_with_env(
            {
                "DISCORD_TOKEN": "token",
                "COMMAND_SYNC_MODE": "off",
                "ENABLE_CORE": "true",
                "ENABLE_INVITE": "1",
                "ENABLE_ORACLES": "false",
            }
        )

        self.assertTrue(loaded.is_cog_enabled("cogs.core"))
        self.assertTrue(loaded.is_cog_enabled("cogs.invite"))
        self.assertFalse(loaded.is_cog_enabled("cogs.oracles"))

    def test_required_core_cannot_be_disabled(self):
        with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
            with mock.patch.dict(
                "os.environ",
                {
                    "DISCORD_TOKEN": "token",
                    "COMMAND_SYNC_MODE": "off",
                    "ENABLE_CORE": "false",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(settings_module.SettingsError, "ENABLE_CORE"):
                    settings_module.load_settings()


if __name__ == "__main__":
    unittest.main()
