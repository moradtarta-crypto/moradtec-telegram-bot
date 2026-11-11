import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from image_relevance import commons_image_matches_topic\n\nfrom scheduled_publish import (
    TOOL_ROTATION,
    build_ffmpeg_command,
    build_photo_caption,
    select_hourly_topic,
    exit_code_for_outcome,
)


class ScheduledPublishingTests(unittest.TestCase):
    def test_safe_skip_is_successful_but_real_failure_is_not(self):
        self.assertEqual(exit_code_for_outcome(None), 0)
        self.assertEqual(exit_code_for_outcome(True), 0)
        self.assertEqual(exit_code_for_outcome(False), 1)

    def test_rotation_covers_all_24_local_hours_without_repeating(self):
        start = datetime(2026, 11, 10, 0, 0, tzinfo=ZoneInfo("Africa/Algiers"))
        selected = [
            select_hourly_topic(start + timedelta(hours=hour))
            for hour in range(24)
        ]
        self.assertEqual(len(selected), 24)
        self.assertEqual(len(set(selected)), 24)
        self.assertEqual(set(selected), set(TOOL_ROTATION))

    def test_selection_uses_algiers_local_hour(self):
        local_time = datetime(2026, 11, 10, 15, 0, tzinfo=ZoneInfo("Africa/Algiers"))
        utc_time = local_time.astimezone(ZoneInfo("UTC"))
        self.assertEqual(select_hourly_topic(local_time), select_hourly_topic(utc_time))

    def test_ffmpeg_command_builds_six_second_h264_mp4(self):
        command = build_ffmpeg_command("/tmp/source.jpg", "/tmp/output.mp4")
        self.assertEqual(command[0], "ffmpeg")
        self.assertIn("libx264", command)
        self.assertIn("1280x720", " ".join(command))
        self.assertEqual(command[command.index("-t") + 1], "6")
        self.assertEqual(command[-1], "/tmp/output.mp4")

    def test_commons_image_requires_multiple_meaningful_topic_matches(self):\n        self.assertFalse(commons_image_matches_topic(\n            "ChatGPT AI language learning",\n            "Knowles Assumptions about Adult Learning.png",\n        ))\n        self.assertTrue(commons_image_matches_topic(\n            "AI language learning",\n            "Language Learning with Artificial Intelligence.jpg",\n        ))\n\n    def test_photo_caption_keeps_a_useful_explanation(self):\n        tool = {"title": "ChatGPT", "description": "An AI assistant for conversation and learning."}\n        caption = build_photo_caption(\n            tool,\n            "يمكنك التدرب على المحادثة وطلب شرح المفردات والقواعد وإنشاء تمارين لغوية.",\n            "https://shrtfly.com/example",\n            shortened=True,\n        )\n        self.assertIn("التدرب على المحادثة", caption)\n\n    def test_photo_caption_stays_within_telegram_limit(self):
        tool = {
            "title": "Example AI Tool",
            "description": "A useful AI tool for creative work.",
        }
        caption = build_photo_caption(
            tool,
            "شرح " * 500,
            "https://shrtfly.com/example",
            shortened=True,
            attribution="📷 Wikimedia Commons",
        )
        self.assertLessEqual(len(caption), 1024)
        self.assertIn("https://shrtfly.com/example", caption)


if __name__ == "__main__":
    unittest.main()
