import unittest
from types import SimpleNamespace

import bot as bot_module
from config.settings import CogFlag


class DummyBot:
    def __init__(self, fail_on=None):
        self.fail_on = set(fail_on or [])
        self.loaded = []

    async def load_extension(self, extension):
        if extension in self.fail_on:
            raise RuntimeError("boom")
        self.loaded.append(extension)


def make_settings(enabled):
    flags = (
        CogFlag("cogs.core", "ENABLE_CORE", True, "core", True),
        CogFlag("cogs.admin", "ENABLE_ADMIN", True, "admin", True),
        CogFlag("cogs.invite", "ENABLE_INVITE", False, "invite", False),
        CogFlag("cogs.roll", "ENABLE_ROLL", False, "roll", False),
        CogFlag("cogs.eight_ball", "ENABLE_EIGHT_BALL", False, "eight ball", False),
        CogFlag("cogs.fortune", "ENABLE_FORTUNE", False, "fortune", False),
    )

    return SimpleNamespace(
        cog_flags=flags,
        is_cog_enabled=lambda extension: enabled.get(extension, False),
    )


class CogLoaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_cogs_load_and_disabled_cogs_skip(self):
        dummy = DummyBot()
        runtime_settings = make_settings(
            {
                "cogs.core": True,
                "cogs.admin": True,
                "cogs.invite": False,
                "cogs.roll": True,
                "cogs.eight_ball": False,
                "cogs.fortune": True,
            }
        )

        with self.assertLogs("wilhelmina", level="INFO") as logs:
            report = await bot_module.load_cogs(dummy, runtime_settings)

        self.assertEqual(dummy.loaded, ["cogs.core", "cogs.admin", "cogs.roll", "cogs.fortune"])
        self.assertEqual(report["loaded"], ["cogs.core", "cogs.admin", "cogs.roll", "cogs.fortune"])
        self.assertEqual(report["skipped"], ["cogs.invite", "cogs.eight_ball"])
        self.assertIn("cog_skipped extension=cogs.eight_ball", "\n".join(logs.output))

    async def test_optional_failed_cog_logs_and_loading_continues(self):
        dummy = DummyBot(fail_on={"cogs.eight_ball"})
        runtime_settings = make_settings(
            {
                "cogs.core": True,
                "cogs.admin": True,
                "cogs.roll": True,
                "cogs.eight_ball": True,
                "cogs.fortune": True,
            }
        )

        with self.assertLogs("wilhelmina", level="INFO") as logs:
            report = await bot_module.load_cogs(dummy, runtime_settings)

        self.assertEqual(dummy.loaded, ["cogs.core", "cogs.admin", "cogs.roll", "cogs.fortune"])
        self.assertEqual(report["failed"], ["cogs.eight_ball"])
        self.assertIn("cog_load_failed_unexpected extension=cogs.eight_ball", "\n".join(logs.output))

    async def test_required_failed_cog_raises(self):
        dummy = DummyBot(fail_on={"cogs.admin"})
        runtime_settings = make_settings(
            {
                "cogs.core": True,
                "cogs.admin": True,
                "cogs.roll": True,
            }
        )

        with self.assertRaises(RuntimeError):
            await bot_module.load_cogs(dummy, runtime_settings)


if __name__ == "__main__":
    unittest.main()
