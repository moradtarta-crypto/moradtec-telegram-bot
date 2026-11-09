import unittest
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

    def test_check_serializes_without_secrets(self):
        item = Check("secret_hygiene", False, "Possible secret; value hidden.", "critical")
        self.assertEqual(item.as_dict()["severity"], "critical")
        self.assertNotIn("token-value", str(item.as_dict()))


if __name__ == "__main__":
    unittest.main()
