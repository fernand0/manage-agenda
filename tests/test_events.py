import datetime
import unittest
from unittest.mock import MagicMock, patch

from manage_agenda.events import adjust_event_times, update_event_status_cli
from manage_agenda.sources import Args


class TestEvents(unittest.TestCase):
    def test_adjust_event_times_both_present(self):
        event = {
            "start": {"dateTime": "2024-01-01T10:00:00"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }
        result = adjust_event_times(event)
        self.assertEqual(result["start"]["dateTime"], "2024-01-01T09:00:00+00:00")
        self.assertEqual(result["end"]["dateTime"], "2024-01-01T10:00:00+00:00")
        self.assertEqual(result["start"]["timeZone"], "UTC")
        self.assertEqual(result["end"]["timeZone"], "UTC")

    def test_adjust_event_times_start_missing(self):
        event = {"end": {"dateTime": "2024-01-01T11:00:00"}}
        result = adjust_event_times(event)
        self.assertEqual(result["start"]["dateTime"], "2024-01-01T09:30:00+00:00")
        self.assertEqual(result["start"]["timeZone"], "UTC")

    def test_adjust_event_times_end_missing(self):
        event = {"start": {"dateTime": "2024-01-01T10:00:00"}}
        result = adjust_event_times(event)
        self.assertEqual(result["end"]["dateTime"], "2024-01-01T09:30:00+00:00")
        self.assertEqual(result["end"]["timeZone"], "UTC")

    def test_adjust_event_times_timezones(self):
        event = {
            "start": {"dateTime": "2024-01-01T10:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2024-01-01T11:00:00", "timeZone": "UTC"},
        }
        result = adjust_event_times(event)
        self.assertEqual(result["start"]["timeZone"], "UTC")
        self.assertEqual(result["end"]["timeZone"], "UTC")

    @patch("manage_agenda.events.select_events_by_user_input", return_value=[])
    @patch("manage_agenda.events.display_posts")
    @patch("manage_agenda.events.select_calendar_from_all_rules")
    def test_update_event_status_uses_calendar_posts(
        self,
        mock_select_calendar,
        mock_display_posts,
        mock_select_events,
    ):
        args = Args(interactive=False, output="", text="")
        api_cal = MagicMock()
        events = [{"summary": "Event", "transparency": "opaque"}]
        api_cal.getPosts.return_value = events
        api_cal.getPostTitle.return_value = "Event"
        mock_select_calendar.return_value = (api_cal, "calendar-id")

        update_event_status_cli(args)

        api_cal.setActive.assert_called_once_with("calendar-id")
        api_cal.setPosts.assert_called_once_with(
            max_results=None, event_types="default", show_active=False
        )
        mock_display_posts.assert_called_once()
        assert mock_display_posts.call_args.args[:2] == (api_cal, events)
        assert mock_display_posts.call_args.kwargs["limit"] == 20
        assert mock_display_posts.call_args.kwargs["title"] == "Upcoming events (up to 20):"
        mock_select_events.assert_called_once_with(api_cal, events, "update")

    def test_adjust_event_times_end_before_start(self):
        """Test adjust_event_times when end is before start."""
        event = {
            "start": {"dateTime": "2024-01-01T11:00:00"},
            "end": {"dateTime": "2024-01-01T10:00:00"},
        }
        result = adjust_event_times(event)

        # End should be adjusted to be 30 minutes after start
        start_dt = datetime.datetime.fromisoformat(result["start"]["dateTime"])
        end_dt = datetime.datetime.fromisoformat(result["end"]["dateTime"])
        self.assertGreater(end_dt, start_dt)

    def test_adjust_event_times_invalid_timezone(self):
        """Test adjust_event_times with invalid timezone."""
        event = {
            "start": {"dateTime": "2024-01-01T10:00:00", "timeZone": "Invalid/Timezone"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }
        result = adjust_event_times(event)

        # Should fallback to default timezone
        self.assertEqual(result["start"]["timeZone"], "UTC")

    @patch("manage_agenda.events.select_calendar_from_all_rules")
    @patch("builtins.input", side_effect=["meeting", "0"])
    def test_copy_events_cli_basic(self, mock_input, mock_select_cal):
        """Test copy_events_cli basic flow."""
        from manage_agenda.events import copy_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        mock_events = {
            "items": [
                {
                    "summary": "Team meeting",
                    "description": "Weekly sync",
                    "start": {"dateTime": "2024-01-15T10:00:00"},
                    "end": {"dateTime": "2024-01-15T11:00:00"},
                }
            ]
        }
        mock_client.events().list().execute.return_value = mock_events
        mock_api.getPostTitle.return_value = "Team meeting"
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_cal.side_effect = [(mock_api, "calendar1"), (mock_api, "calendar2")]

        copy_events_cli(args)

        mock_client.events().insert.assert_called()

    @patch("manage_agenda.events.select_calendar_from_all_rules")
    @patch("builtins.input", side_effect=["", "0"])
    def test_delete_events_cli_basic(self, mock_input, mock_select_cal):
        """Test delete_events_cli basic flow."""
        from manage_agenda.events import delete_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        mock_events = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Old meeting",
                    "start": {"dateTime": "2024-01-15T10:00:00"},
                    "end": {"dateTime": "2024-01-15T11:00:00"},
                }
            ]
        }
        mock_client.events().list().execute.return_value = mock_events
        mock_api.getPostTitle.return_value = "Old meeting"
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_cal.return_value = (mock_api, "calendar1")

        delete_events_cli(args)

        mock_client.events().delete.assert_called()

    @patch("manage_agenda.events.select_calendar_from_all_rules")
    @patch("builtins.input", side_effect=["", "0"])
    def test_move_events_cli_basic(self, mock_input, mock_select_cal):
        """Test move_events_cli basic flow."""
        from manage_agenda.events import move_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        mock_events = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Moving meeting",
                    "start": {"dateTime": "2024-01-15T10:00:00"},
                    "end": {"dateTime": "2024-01-15T11:00:00"},
                }
            ]
        }
        mock_client.events().list().execute.return_value = mock_events
        mock_api.getPostTitle.return_value = "Moving meeting"
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_cal.side_effect = [(mock_api, "calendar1"), (mock_api, "calendar2")]

        move_events_cli(args)

        mock_client.events().insert.assert_called()
        mock_client.events().delete.assert_called()

    def test_parse_datetime_value(self):
        """Test _parse_datetime_value handles datetimes, dates, and strings."""
        from manage_agenda.events import _parse_datetime_value

        dt, is_date = _parse_datetime_value(None)
        self.assertIsNone(dt)
        self.assertFalse(is_date)

        now = datetime.datetime(2026, 9, 20, 10, 0, 0)
        dt, is_date = _parse_datetime_value(now)
        self.assertEqual(dt, now)
        self.assertFalse(is_date)

        today = datetime.date(2026, 9, 20)
        dt, is_date = _parse_datetime_value(today)
        self.assertEqual(dt.date(), today)
        self.assertTrue(is_date)

        dt, is_date = _parse_datetime_value("2026-09-20")
        self.assertEqual(dt.strftime("%Y-%m-%d"), "2026-09-20")
        self.assertTrue(is_date)

        dt, is_date = _parse_datetime_value("2026-09-20T10:00:00")
        self.assertEqual(dt.strftime("%Y-%m-%d %H:%M"), "2026-09-20 10:00")
        self.assertFalse(is_date)

    def test_format_event_time_range(self):
        """Test format_event_time_range for same-day, cross-day, and date-only ranges."""
        from manage_agenda.events import format_event_time_range

        same_day = format_event_time_range("2026-09-20T10:00:00", "2026-09-20T11:00:00")
        self.assertEqual(same_day, "2026-09-20 10:00 to 11:00")

        diff_days = format_event_time_range("2026-09-20T10:00:00", "2026-09-21T11:00:00")
        self.assertEqual(diff_days, "2026-09-20 10:00 to 2026-09-21 11:00")

        date_only_same = format_event_time_range("2026-09-20", "2026-09-20")
        self.assertEqual(date_only_same, "2026-09-20")

        date_only_diff = format_event_time_range("2026-09-20", "2026-09-22")
        self.assertEqual(date_only_diff, "2026-09-20 to 2026-09-22")

        start_only = format_event_time_range("2026-09-20T10:00:00", None)
        self.assertEqual(start_only, "2026-09-20 10:00")

    def test_format_event_summary(self):
        """Test format_event_summary formats event dict properly."""
        from manage_agenda.events import format_event_summary

        event = {
            "summary": "Project Sync",
            "start": {"dateTime": "2026-09-20T10:00:00"},
            "end": {"dateTime": "2026-09-20T11:00:00"},
        }
        res = format_event_summary(event)
        self.assertEqual(res, "- Project Sync (2026-09-20 10:00 to 11:00)")

        event_no_dates = {"summary": "Quick Note"}
        res_no_dates = format_event_summary(event_no_dates)
        self.assertEqual(res_no_dates, "- Quick Note")

    def test_print_events_summary(self):
        """Test print_events_summary outputs summary to stdout."""
        import io
        import sys
        from manage_agenda.events import print_events_summary

        events = [
            {
                "summary": "Meeting with Alice",
                "start": {"dateTime": "2026-09-20T10:00:00"},
                "end": {"dateTime": "2026-09-20T11:00:00"},
            },
            {
                "summary": "Conference Day",
                "start": {"date": "2026-09-22"},
                "end": {"date": "2026-09-22"},
            },
        ]

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            print_events_summary(events)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Summary of events added:", output)
        self.assertIn("- Meeting with Alice (2026-09-20 10:00 to 11:00)", output)
        self.assertIn("- Conference Day (2026-09-22)", output)

    def test_print_events_summary_empty(self):
        """Test print_events_summary when no events are added."""
        import io
        import sys
        from manage_agenda.events import print_events_summary

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            print_events_summary([])
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Summary of events added:", output)
        self.assertIn("No events were added.", output)

    def test_display_event_info_basic(self):
        """Test display_event_info with minimal event."""
        import io
        import sys
        from manage_agenda.events import display_event_info

        event = {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-10-21T10:00:00"},
            "end": {"dateTime": "2026-10-21T11:00:00"},
        }
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            display_event_info(event)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("=====================================", output)
        self.assertIn("Summary: Team Sync", output)
        self.assertIn("Start: 2026-10-21 10:00:00", output)
        self.assertIn("End: 2026-10-21 11:00:00", output)
        self.assertNotIn("Model:", output)
        self.assertNotIn("File:", output)
        self.assertNotIn("Time:", output)

    def test_display_event_info_full(self):
        """Test display_event_info with model, elapsed_time, and post_identifier."""
        import io
        import sys
        from unittest.mock import MagicMock
        from manage_agenda.events import display_event_info

        event = {
            "summary": "Keynote",
            "start": {"dateTime": "2026-10-21T09:00:00"},
            "end": {"dateTime": "2026-10-21T10:00:00"},
        }
        mock_model = MagicMock()
        mock_model.model_name = "gemini-2.0-flash"

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            display_event_info(
                event,
                subject_for_print="Fallback Subject",
                elapsed_time=2.5,
                model=mock_model,
                post_identifier="file_123.txt",
            )
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Summary: Keynote", output)
        self.assertIn("File: file_123.txt", output)
        self.assertIn("Model: gemini-2.0-flash", output)
        self.assertIn("Time: 0h 0m 2.50s (2.50 seconds)", output)

    def test_display_event_info_date_only_and_fallback_summary(self):
        """Test display_event_info with date-only start/end and fallback summary."""
        import io
        import sys
        from manage_agenda.events import display_event_info

        event = {
            "start": {"date": "2026-10-21"},
            "end": {"date": "2026-10-22"},
        }
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            display_event_info(event, subject_for_print="Holiday")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Summary: Holiday", output)
        self.assertIn("Start: 2026-10-21", output)
        self.assertIn("End: 2026-10-22", output)

    def test_move_action_verbose_true(self):
        """Test move_action with verbose=True displays event abstract."""
        import io
        import sys
        from unittest.mock import MagicMock
        from manage_agenda.events import move_action

        mock_api = MagicMock()
        mock_api.getActive.return_value = "src_cal"
        mock_dst = MagicMock()

        event = {
            "id": "ev1",
            "summary": "Moved Event",
            "start": {"dateTime": "2026-10-21T10:00:00"},
            "end": {"dateTime": "2026-10-21T11:00:00"},
        }

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            move_action(mock_api, event, "dst_cal", mock_dst, verbose=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Copied event: Moved Event", output)
        self.assertIn("Deleted event: Moved Event", output)
        self.assertIn("=====================================", output)
        self.assertIn("Summary: Moved Event", output)
        self.assertIn("Start: 2026-10-21 10:00:00", output)

    def test_move_action_verbose_false(self):
        """Test move_action with verbose=False does not display event abstract."""
        import io
        import sys
        from unittest.mock import MagicMock
        from manage_agenda.events import move_action

        mock_api = MagicMock()
        mock_api.getActive.return_value = "src_cal"
        mock_dst = MagicMock()

        event = {
            "id": "ev1",
            "summary": "Moved Event",
            "start": {"dateTime": "2026-10-21T10:00:00"},
            "end": {"dateTime": "2026-10-21T11:00:00"},
        }

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            move_action(mock_api, event, "dst_cal", mock_dst, verbose=False)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("Copied event: Moved Event", output)
        self.assertIn("Deleted event: Moved Event", output)
        self.assertNotIn("=====================================", output)
