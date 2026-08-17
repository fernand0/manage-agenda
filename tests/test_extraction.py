import datetime
import sys
import unittest
from unittest.mock import MagicMock, patch

from manage_agenda.extraction import (
    add_message_to_event_description,
    create_event_dict,
    extract_json,
)
from manage_agenda.sources import Args


class TestExtraction(unittest.TestCase):
    def test_extract_json(self):
        text = """Some text

        ```json
{"key": "value"}
        ```

more text"""
        expected_json = '{"key": "value"}'
        self.assertEqual(extract_json(text), expected_json)

    def test_add_message_to_event_description(self):
        event = {"description": "Original description"}
        content = "Email content"
        result = add_message_to_event_description(event, content)
        self.assertIn("Email content", result["description"])

    def test_create_event_dict(self):
        event_dict = create_event_dict()
        self.assertIsInstance(event_dict, dict)
        self.assertIn("summary", event_dict)
        self.assertIn("start", event_dict)

    @patch("manage_agenda.extraction.format_time")
    def test_get_event_from_llm_success(self, mock_format_time):
        """Test get_event_from_llm with successful response."""
        from manage_agenda.extraction import get_event_from_llm

        mock_format_time.return_value = "0h 0m 1.00s"
        mock_model = MagicMock()
        mock_model.generate_text.return_value = (
            '{"summary": "Test Event", "start": {"dateTime": "2024-01-01T10:00:00"}}'
        )

        prompt = "Create an event"
        event, vcal_json, elapsed_time = get_event_from_llm(
            mock_model, prompt, post_id="test_post_123", verbose=False
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["summary"], "Test Event")
        self.assertIsInstance(elapsed_time, float)

    @patch("manage_agenda.extraction.format_time")
    def test_get_event_from_llm_no_response(self, mock_format_time):
        """Test get_event_from_llm when LLM returns no response."""
        import io

        from manage_agenda.extraction import get_event_from_llm

        mock_format_time.return_value = "0h 0m 1.00s"
        mock_model = MagicMock()
        mock_model.generate_text.return_value = ""

        captured_output = io.StringIO()
        sys.stdout = captured_output
        event, vcal_json, elapsed_time = get_event_from_llm(
            mock_model, "test", post_id="test_post_123", verbose=False
        )
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("Failed to get response", output)

    def test_extract_json_with_braces(self):
        """Test extract_json finds JSON within text."""
        text = 'some text before {"key": "value"} some text after'
        result = extract_json(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_json_already_clean(self):
        """Test extract_json with clean JSON."""
        text = '{"key": "value"}'
        result = extract_json(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_json_multiple_braces(self):
        """Test extract_json with nested JSON and extra closing brace."""
        text = '{"key": {"nested": "value"}}}extra'
        result = extract_json(text)
        self.assertIn('"key"', result)
        self.assertIn('"nested"', result)

    def test_create_llm_prompt(self):
        """Test _create_llm_prompt generates correct prompt."""
        from manage_agenda.extraction import _create_llm_prompt

        event = create_event_dict()
        content = "Meeting about project X on Monday at 3pm"
        ref_date = datetime.datetime(2024, 1, 15, 10, 0, 0)

        prompt = _create_llm_prompt(event, content, ref_date)

        self.assertIn("Meeting about project X", prompt)
        self.assertIn("JSON", prompt)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)

    @patch("manage_agenda.extraction.get_event_from_llm")
    @patch("manage_agenda.extraction.select_api")
    @patch("manage_agenda.extraction.select_calendar")
    @patch("manage_agenda.extraction.write_file")
    @patch("manage_agenda.events._validate_event_dates_interactive")
    def test_process_event_with_llm_and_calendar_multiple_events(
        self,
        mock_interactive_confirmation,
        mock_write_file,
        mock_select_calendar,
        mock_select_api,
        mock_get_event_from_llm,
    ):
        """Test _process_event_with_llm_and_calendar when LLM returns a tuple of events."""
        from manage_agenda.extraction import _process_event_with_llm_and_calendar

        args = Args(
            interactive=False,
            delete=False,
            source="gemini",
            verbose=False,
            destination="",
            text="",
        )

        mock_model = MagicMock()
        event1 = {
            "summary": "Meeting One",
            "start": {"dateTime": "2024-01-01T10:00:00"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }
        event2 = {
            "summary": "Meeting Two",
            "start": {"dateTime": "2024-01-02T12:00:00"},
            "end": {"dateTime": "2024-01-02T13:00:00"},
        }

        mock_get_event_from_llm.return_value = ((event1, event2), (event1, event2), 1.0)

        mock_api_dst = MagicMock()
        mock_select_api.return_value = mock_api_dst
        mock_select_calendar.return_value = "calendar_id"
        mock_interactive_confirmation.side_effect = lambda args, ev: ev
        mock_api_dst.publishPost.side_effect = ["result1", "result2"]

        events, results = _process_event_with_llm_and_calendar(
            args,
            mock_model,
            content_text="Multiple events text",
            reference_date_time="2024-01-01T00:00:00",
            post_identifier="post_123",
            subject_for_print="Test Subject",
        )

        self.assertIsInstance(events, list)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["summary"], "Meeting One")
        self.assertEqual(events[1]["summary"], "Meeting Two")
        self.assertEqual(results, ["result1", "result2"])

        self.assertEqual(mock_write_file.call_count, 8)
        self.assertEqual(mock_api_dst.publishPost.call_count, 2)

    @patch("manage_agenda.extraction._extract_event_with_llm_retry")
    @patch("manage_agenda.extraction.select_api")
    @patch("manage_agenda.extraction.select_calendar")
    @patch("manage_agenda.extraction.write_file")
    @patch("manage_agenda.events._validate_event_dates_interactive")
    def test_process_event_with_llm_and_calendar_file_output(
        self,
        mock_interactive_confirmation,
        mock_write_file,
        mock_select_calendar,
        mock_select_api,
        mock_extract_event_with_llm_retry,
    ):
        """Test _process_event_with_llm_and_calendar with file output option."""
        from manage_agenda.extraction import _process_event_with_llm_and_calendar

        args = Args(
            interactive=False,
            delete=False,
            source="gemini",
            verbose=False,
            destination="",
            text="",
            output="file",
        )

        mock_model = MagicMock()
        event = {
            "summary": "Meeting One",
            "start": {"dateTime": "2024-01-01T10:00:00"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }

        mock_extract_event_with_llm_retry.return_value = ([event], event, 1.0, True, False, False)
        mock_interactive_confirmation.side_effect = lambda args, ev, *a, **kw: (ev, False)

        events, results = _process_event_with_llm_and_calendar(
            args,
            mock_model,
            content_text="Single event text",
            reference_date_time="2024-01-01T00:00:00",
            post_identifier="post_123",
            subject_for_print="Test Subject",
        )

        self.assertEqual(events[0]["summary"], "Meeting One")
        self.assertEqual(results, ["post_123_1_times.json"])

        mock_select_api.assert_not_called()
        mock_select_calendar.assert_not_called()
        mock_write_file.assert_called()
