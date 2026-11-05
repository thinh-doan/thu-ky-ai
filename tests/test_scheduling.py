import unittest
from datetime import date, datetime, timezone

from scheduling.candidates import generate_slots
from scheduling.models import BusyEvent, SchedulingRequest, UserProfile


class SchedulingTests(unittest.TestCase):
    def test_excludes_conflicting_slots_and_keeps_buffer(self):
        busy = [
            BusyEvent(
                datetime(2026, 11, 6, 9, tzinfo=timezone.utc),
                datetime(2026, 11, 6, 10, tzinfo=timezone.utc),
            )
        ]
        request = SchedulingRequest(
            "Study", 60, date(2026, 11, 6), date(2026, 11, 6), min_buffer_minutes=30
        )
        slots = generate_slots(request, busy, UserProfile(habit_hours={"study": (14.0,)}))
        self.assertTrue(slots)
        self.assertTrue(all(slot.start.hour != 9 for slot in slots))
        self.assertTrue(all(slot.start.hour != 10 for slot in slots))

    def test_personal_habit_changes_ranking(self):
        request = SchedulingRequest(
            "Personal", 60, date(2026, 11, 6), date(2026, 11, 6), max_results=3
        )
        slots = generate_slots(
            request,
            [],
            UserProfile(habit_hours={"personal": (18.0,)}),
        )
        self.assertEqual(slots[0].start.hour, 18)
        self.assertIn("Phù hợp thói quen cá nhân", slots[0].reasons)


if __name__ == "__main__":
    unittest.main()
