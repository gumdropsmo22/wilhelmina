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
        CogFlag("cogs.invite", "ENABLE_INVITE", False, "invite", False),
        CogFlag("cogs.oracles", "ENABLE_ORACLES", False, "oracles", False),
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
                "cogs.invite": True,
                "cogs.oracles": False,
            }
        )

        with self.assertLogs("wilhelmina", level="INFO") as logs:
            report = await bot_module.load_cogs(dummy, runtime_settings)

        self.assertEqual(dummy.loaded, ["cogs.core", "cogs.invite"])
        self.assertEqual(report["loaded"], ["cogs.core", "cogs.invite"])
        self.assertEqual(report["skipped"], ["cogs.oracles"])
        self.assertIn("cog_skipped extension=cogs.oracles", "\n".join(logs.output))

    async def test_optional_failed_cog_logs_and_loading_continues(self):
        dummy = DummyBot(fail_on={"cogs.invite"})
        runtime_settings = make_settings(
            {
                "cogs.core": True,
                "cogs.invite": True,
                "cogs.oracles": True,
            }
        )

        with self.assertLogs("wilhelmina", level="INFO") as logs:
            report = await bot_module.load_cogs(dummy, runtime_settings)

        self.assertEqual(dummy.loaded, ["cogs.core", "cogs.oracles"])
        self.assertEqual(report["failed"], ["cogs.invite"])
        self.assertIn("cog_load_failed_unexpected extension=cogs.invite", "\n".join(logs.output))

    async def test_required_failed_cog_raises(self):
        dummy = DummyBot(fail_on={"cogs.core"})
        runtime_settings = make_settings(
            {
                "cogs.core": True,
                "cogs.invite": True,
                "cogs.oracles": True,
            }
        )

        with self.assertRaises(RuntimeError):
            await bot_module.load_cogs(dummy, runtime_settings)


if __name__ == "__main__":
    unittest.main()
