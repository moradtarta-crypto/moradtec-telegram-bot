import unittest

from self_developer import ProposalValidationError, validate_generated_python


class ProposalValidationTests(unittest.TestCase):
    def test_accepts_small_pure_python_module(self):
        source = '"""Example."""\n\ndef add(a: int, b: int) -> int:\n    return a + b\n'
        self.assertIn("def add", validate_generated_python(source))

    def test_strips_outer_markdown_fence(self):
        fence = chr(96) * 3
        source = fence + "python\ndef double(value: int) -> int:\n    return value * 2\n" + fence
        self.assertIn("def double", validate_generated_python(source))

    def test_rejects_unapproved_import(self):
        with self.assertRaises(ProposalValidationError):
            validate_generated_python("import os\ndef f():\n    return 1\n")

    def test_rejects_dynamic_execution(self):
        with self.assertRaises(ProposalValidationError):
            validate_generated_python("def f(code):\n    return eval(code)\n")

    def test_rejects_syntax_error(self):
        with self.assertRaises(ProposalValidationError):
            validate_generated_python("def broken(:\n")

    def test_requires_a_definition(self):
        with self.assertRaises(ProposalValidationError):
            validate_generated_python("VALUE = 10\n")


if __name__ == "__main__":
    unittest.main()
