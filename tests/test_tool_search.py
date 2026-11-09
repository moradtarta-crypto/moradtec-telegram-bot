import unittest

from tool_search import (
    canonical_tool_url,
    deduplicate_tool_results,
    is_relevant_tool,
    normalize_search_text,
    task_category,
)


class ToolSearchTests(unittest.TestCase):
    def test_normalizes_arabic_diacritics_and_alef(self):
        self.assertEqual(normalize_search_text("إِنْشَاءُ فِيدْيُو"), "انشاء فيديو")

    def test_detects_arabic_and_english_categories(self):
        self.assertEqual(task_category("إنشاء فيديو بالذكاء الاصطناعي"), "video")
        self.assertEqual(task_category("data analytics"), "data")
        self.assertEqual(task_category("تحويل النص إلى صوت"), "voice")

    def test_rejects_unrelated_and_directory_results(self):
        self.assertFalse(is_relevant_tool(
            "إنشاء فيديو",
            title="Adoptium - Java runtime",
            url="https://adoptium.net",
            description="Tools for Java developers",
        ))
        self.assertFalse(is_relevant_tool(
            "إنشاء فيديو",
            title="Best AI tools directory",
            url="https://example.com",
            description="Directory of AI tools",
        ))

    def test_accepts_matching_product_metadata(self):
        self.assertTrue(is_relevant_tool(
            "إنشاء فيديو",
            title="AI Video Generator",
            url="https://video.example.com",
            description="Create videos from text with AI",
        ))

    def test_accepts_body_evidence_only_for_identified_product(self):
        self.assertTrue(is_relevant_tool(
            "إنشاء فيديو",
            title="Example Studio",
            url="https://studio.example.com",
            description="Creative platform",
            content="This platform includes an AI video generator and text-to-video workflow.",
        ))
        self.assertFalse(is_relevant_tool(
            "إنشاء فيديو",
            title="Example Company",
            url="https://example.com",
            description="Company news",
            content="Our research mentions video generation.",
        ))

    def test_canonical_url_removes_tracking_and_fragment(self):
        self.assertEqual(
            canonical_tool_url("https://www.example.com/product/?utm_source=x#pricing"),
            "https://example.com/product",
        )

    def test_rejects_non_https_private_and_credential_urls(self):
        self.assertIsNone(canonical_tool_url("http://example.com"))
        self.assertIsNone(canonical_tool_url("https://127.0.0.1"))
        self.assertIsNone(canonical_tool_url("https://user:pass@example.com"))

    def test_deduplicates_hosts_and_invalid_urls(self):
        tools = [
            {"title": "A", "url": "https://www.example.com/?utm_source=a"},
            {"title": "A duplicate", "url": "https://example.com/another-page"},
            {"title": "B", "url": "https://other.example.org"},
            {"title": "Bad", "url": "http://unsafe.example"},
        ]
        result = deduplicate_tool_results(tools)
        self.assertEqual([item["title"] for item in result], ["A", "B"])
        self.assertEqual(result[0]["url"], "https://example.com/")


if __name__ == "__main__":
    unittest.main()
