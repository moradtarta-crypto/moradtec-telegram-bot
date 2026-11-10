import unittest

from tool_catalog import catalog_tools_for_query


class ToolCatalogTests(unittest.TestCase):
    def test_video_task_uses_verified_deepai_official_page(self):
        tools = catalog_tools_for_query("إنشاء فيديو بالذكاء الاصطناعي")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["title"], "DeepAI AI Video Generator")
        self.assertEqual(tools[0]["url"], "https://deepai.org/video")

    def test_english_video_query_uses_catalog(self):
        self.assertEqual(
            [item["url"] for item in catalog_tools_for_query("AI video generator")],
            ["https://deepai.org/video"],
        )

    def test_direct_deepai_brand_lookup_returns_official_page(self):
        tools = catalog_tools_for_query("DeepAI")
        self.assertEqual([item["url"] for item in tools], ["https://deepai.org/video"])

    def test_translation_task_returns_deepl_not_video_tool(self):
        tools = catalog_tools_for_query("ترجمة النصوص")
        self.assertEqual([item["url"] for item in tools], [
            "https://deepl.com/en/translator"
        ])
        self.assertEqual(tools[0]["title"], "DeepL Translator")

    def test_unrelated_task_does_not_receive_video_tool(self):
        tools = catalog_tools_for_query("تصميم الأزياء")
        self.assertNotIn("https://deepai.org/video", [item["url"] for item in tools])


if __name__ == "__main__":
    unittest.main()
