import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scheduled_publish import (
    TOOL_ROTATION,
    build_photo_caption,
    select_hourly_topic,
)


class ScheduledPublishingTests(unittest.TestCase):
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

    def test_photo_caption_stays_within_telegram_limit(self):
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
