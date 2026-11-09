import unittest

from tool_explainer import build_grounded_explanation


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
        self.assertIn("لم أستنتج أن الخدمة مجانية", explanation)

    def test_does_not_invent_features_when_source_is_vague(self):
        explanation = build_grounded_explanation({
            "title": "Example AI",
            "description": "A helpful AI platform.",
            "content": "Welcome to our platform.",
        }, "إنشاء فيديو")
        self.assertIsNone(explanation)

    def test_text_only_feature_does_not_claim_image_to_video(self):
        explanation = build_grounded_explanation({
            "title": "Text Video Maker",
            "description": "Text to video generator.",
            "content": "Enter a prompt to create videos from text.",
        }, "إنشاء فيديو")
        self.assertIn("Text to Video", explanation)
        self.assertNotIn("Image to Video", explanation)
        self.assertNotIn("تعديل فيديو موجود", explanation)


if __name__ == "__main__":
    unittest.main()
