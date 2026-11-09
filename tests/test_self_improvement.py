import unittest
from unittest import mock
from pathlib import Path
from tempfile import TemporaryDirectory

from self_improvement import Check, _clean_ai_report, _fallback_ai_report, run_self_check


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

    def test_repeated_ai_output_falls_back_to_factual_report(self):
        checks = [Check("python_syntax", True, "bot.py syntax is valid.", "critical")]
        repeated = "مراجعة عامة لصحة البوت جيدة. " + ("يجب تحسين التحكم في الملكية الخاصة بالملك. " * 5)
        result = _clean_ai_report(repeated, checks)
        self.assertIn("جميع الفحوصات اجتازت الاختبار", result)
        self.assertNotIn("الملكية الخاصة بالملك", result)

    def test_clean_ai_report_removes_duplicate_sentences(self):
        checks = [Check("python_syntax", False, "SyntaxError detected.", "critical")]
        answer = "تعذر تحليل الملف بسبب خطأ نحوي واضح. يجب إصلاح الخطأ ثم إعادة الفحص. تعذر تحليل الملف بسبب خطأ نحوي واضح."
        result = _clean_ai_report(answer, checks)
        self.assertEqual(result.count("تعذر تحليل الملف بسبب خطأ نحوي واضح"), 1)
        self.assertLessEqual(len(result), 1100)

    def test_all_pass_rejects_ai_claims_of_missing_repairs(self):
        checks = [
            Check("owner_tools_registered", True, "Self-improvement commands are registered."),
            Check("secret_hygiene", True, "No obvious hard-coded API token assignment was found."),
        ]
        misleading = (
            "النتائج الناجحة جيدة. النتائج الفاشلة: owner_tools_registered لا يوجد إجراء إصلاح. "
            "secret_hygiene لا يوجد إجراء إصلاح."
        )
        result = _clean_ai_report(misleading, checks)
        self.assertIn("جميع الفحوصات اجتازت الاختبار", result)
        self.assertNotIn("لا يوجد إجراء إصلاح", result)

    def test_fallback_report_does_not_overclaim(self):
        checks = [Check("python_syntax", True, "bot.py syntax is valid.", "critical")]
        result = _fallback_ai_report(checks)
        self.assertIn("تغطي الفحوصات المحددة فقط", result)
        self.assertNotIn("آمن تماماً", result)

    def test_check_serializes_without_secrets(self):
        item = Check("secret_hygiene", False, "Possible secret; value hidden.", "critical")
        self.assertEqual(item.as_dict()["severity"], "critical")
        self.assertNotIn("token-value", str(item.as_dict()))


if __name__ == "__main__":
    unittest.main()
