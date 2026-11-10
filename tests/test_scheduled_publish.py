import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduled_publish import TOOL_ROTATION, select_daily_tool


class ScheduledPublishingTests(unittest.TestCase):
    def test_three_slots_select_different_tools_for_same_day(self):
        now = datetime(2026, 11, 10, 10, 0, tzinfo=ZoneInfo("Africa/Algiers"))
        selected = [select_daily_tool(now, slot) for slot in ("morning", "afternoon", "evening")]
        self.assertEqual(len(set(selected)), 3)

    def test_rotation_stays_within_curated_catalog(self):
        now = datetime(2026, 11, 10, 12, 0, tzinfo=ZoneInfo("Africa/Algiers"))
        for slot in ("morning", "afternoon", "evening"):
            self.assertIn(select_daily_tool(now, slot), TOOL_ROTATION)

    def test_rejects_unknown_slot(self):
        now = datetime(2026, 11, 10, 12, 0, tzinfo=ZoneInfo("Africa/Algiers"))
        with self.assertRaises(ValueError):
            select_daily_tool(now, "night")


if __name__ == "__main__":
    unittest.main()
