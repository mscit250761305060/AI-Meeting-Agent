import unittest

from server import meeting_state
from agents.meeting_connector_agent import classify_meeting_url


class MeetingRuntimeTests(unittest.TestCase):
    def setUp(self):
        meeting_state.reset_runtime_state()

    def test_begin_and_end_meeting_lifecycle(self):
        self.assertTrue(meeting_state.begin_meeting())
        self.assertTrue(meeting_state.meeting_running)
        self.assertTrue(meeting_state.end_meeting())
        self.assertFalse(meeting_state.meeting_running)

    def test_start_runtime_rejects_duplicate_lifecycle(self):
        self.assertTrue(meeting_state.start_runtime())
        self.assertFalse(meeting_state.start_runtime())

    def test_classify_meeting_urls(self):
        self.assertEqual(classify_meeting_url("https://meet.google.com/abc-defg-hij"), "google")
        self.assertEqual(classify_meeting_url("https://zoom.us/j/123456"), "zoom")
        self.assertEqual(classify_meeting_url("https://teams.microsoft.com/l/meetup-join/abc"), "teams")
        self.assertIsNone(classify_meeting_url("https://example.com"))


if __name__ == "__main__":
    unittest.main()
