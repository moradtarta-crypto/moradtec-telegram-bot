import unittest

from tool_post import build_tool_post


class ToolPostTests(unittest.TestCase):
    def test_builds_arabic_post_with_disclosure_and_short_link(self):
        post = build_tool_post(
            {"title": "AI Video Studio", "description": "Create short videos from text prompts.", "url": "https://official.example"},
            "تتيح الصفحة إنشاء فيديو من وصف نصي.",
            "https://shrtslug.biz/example",
        )
        self.assertIn("AI Video Studio", post)
        self.assertIn("Create short videos", post)
        self.assertIn("https://shrtslug.biz/example", post)
        self.assertIn("صفحة إعلانية", post)
        self.assertNotIn("https://official.example", post)

    def test_falls_back_without_inventing_how_to_steps(self):
        post = build_tool_post({"title": "Example Tool", "description": ""}, "", "https://example.com")
        self.assertIn("لا تتوفر", post)
        self.assertIn("راجع الموقع الرسمي", post)

    def test_limits_output_length(self):
        post = build_tool_post({"title": "Tool", "description": "x" * 5000}, "y" * 5000, "https://example.com")
        self.assertLessEqual(len(post), 3400)


if __name__ == "__main__":
    unittest.main()
