import unittest
from unittest import mock
from pathlib import Path
from tempfile import TemporaryDirectory

from self_improvement import Check, run_self_check


class SelfImprovementTests(unittest.TestCase):
    def test_detects_invalid_python(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bot.py").write_text("def broken(:\n", encoding="utf-8")
            checks = run_self_check(root)
            self.assertFalse(checks[0].ok)
            self.assertEqual(checks[0].name, "python_syntax")

    def test_detects_missing_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bot.py").write_text("x = 1\n", encoding="utf-8")
            checks = run_self_check(root)
            manifest = next(item for item in checks if item.name == "dependencies_manifest")
            self.assertFalse(manifest.ok)

    def test_detects_registered_command_handlers_without_ast_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = "\n".join([
                "from telegram.ext import CommandHandler",
                "app.add_handler(CommandHandler('start', start))",
                "app.add_handler(CommandHandler('help', help_command))",
                "app.add_handler(CommandHandler('selfcheck', selfcheck_command))",
                "app.add_handler(CommandHandler('improve', improve_command))",
                "app.add_handler(CommandHandler('autodev', autodev_command))",
                "def guard(update): return is_owner(update)",
                "secret_token=WEBHOOK_SECRET",
            ])
            (root / "bot.py").write_text(source, encoding="utf-8")
            (root / "requirements.txt").write_text("httpx", encoding="utf-8")
            with mock.patch.dict("os.environ", {
                "BOT_TOKEN": "configured",
                "OWNER_ID": "123",
                "CHANNEL_ID": "@example",
            }):
                checks = run_self_check(root)
            commands = next(item for item in checks if item.name == "owner_tools_registered")
            self.assertTrue(commands.ok, commands.detail)

    def test_check_serializes_without_secrets(self):
        item = Check("secret_hygiene", False, "Possible secret; value hidden.", "critical")
        self.assertEqual(item.as_dict()["severity"], "critical")
        self.assertNotIn("token-value", str(item.as_dict()))


if __name__ == "__main__":
    unittest.main()
