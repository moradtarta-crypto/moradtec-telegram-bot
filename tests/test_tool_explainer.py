import unittest

from tool_explainer import build_grounded_explanation, hide_direct_links


class GroundedToolExplanationTests(unittest.TestCase):
    def test_builds_video_guide_from_explicit_capabilities(self):
        explanation = build_grounded_explanation({
            "title": "DeepAI Video Generator",
            "description": "Create videos from text or images.",
            "url": "https://deepai.org/video",
            "content": (
                "Text to video. Image to Video. Video Edit. "
                "By uploading you give the right to share the image and video publicly."
            ),
        }, "إنشاء فيديو بالذكاء الاصطناعي")
        self.assertIsNotNone(explanation)
        self.assertIn("Text to Video", explanation)
        self.assertIn("Image to Video", explanation)
        self.assertIn("تعديل فيديو موجود", explanation)
        self.assertIn("تنبيه خصوصية", explanation)
        self.assertIn("25 ثانية HD", explanation)
        self.assertIn("https://deepai.org/docs", explanation)

    def test_hides_direct_urls_when_short_link_is_available(self):
        explanation = (
            "طريقة الاستخدام: افتح https://deepai.org/video\n"
            "المراجع الرسمية: https://deepai.org/docs | https://deepai.org/video"
        )
        cleaned = hide_direct_links(explanation)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("المراجع الرسمية:", cleaned)
        self.assertIn("افتح الأداة من الرابط المختصر الموجود أسفل الشرح.", cleaned)
        self.assertNotIn("افتح صفحة مولّد الفيديو الرسمية:", cleaned)

    def test_does_not_invent_features_when_source_is_vague(self):
        explanation = build_grounded_explanation({
            "title": "Example AI",
            "description": "A helpful AI platform.",
            "content": "Welcome to our platform.",
            "url": "https://example.com",
        }, "إنشاء فيديو")
        self.assertIsNone(explanation)

    def test_text_only_feature_does_not_claim_image_to_video(self):
        explanation = build_grounded_explanation({
            "title": "Text Video Maker",
            "description": "Text to video generator.",
            "content": "Enter a prompt to create videos from text.",
            "url": "https://example.com",
        }, "إنشاء فيديو")
        self.assertIn("Text to Video", explanation)
        self.assertNotIn("Image to Video", explanation)
        self.assertNotIn("تعديل فيديو موجود", explanation)

    def test_deepai_homepage_uses_official_video_guide(self):
        explanation = build_grounded_explanation({
            "title": "DeepAI",
            "description": "Explore our AI generators.",
            "content": "AI Video Generator. Create short videos.",
            "url": "https://www.deepai.org/",
        }, "إنشاء فيديو بالذكاء الاصطناعي")
        self.assertIn("Text to Video", explanation)
        self.assertIn("Image to Video", explanation)
        self.assertIn("0.20 دولار/ثانية", explanation)
        self.assertIn("0.30 دولار/ثانية", explanation)
        self.assertIn("حق مشاركة الصورة والفيديو علناً", explanation)
        self.assertIn("https://deepai.org/docs", explanation)


if __name__ == "__main__":
    unittest.main()
