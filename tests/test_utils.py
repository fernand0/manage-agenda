import datetime
import sys
import unittest
from collections import namedtuple
from email.utils import formatdate
from unittest.mock import MagicMock, patch

from socialModules.configMod import select_from_list

from manage_agenda.utils import (
    Args,
    adjust_event_times,
    authorize,
    create_event_dict,
    extract_json,
    get_cached_rules,
    list_emails_folder,
    list_events_folder,
    process_email_cli,
    process_event_data,
    reset_cached_rules,
    safe_get,
    select_api_source,
    select_calendar,
    select_llm,
)

# from manage_agenda.utils_base import select_from_list


class TestProcessEmailCli(unittest.TestCase):
    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.utils.select_api_source")
    @patch("manage_agenda.utils.select_email_source")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("manage_agenda.utils.moduleRules.moduleRules")
    @patch("manage_agenda.utils.select_calendar")
    @patch("manage_agenda.utils.write_file")
    @patch("manage_agenda.utils.json.loads")
    @patch("manage_agenda.utils.input", return_value="")
    @patch("manage_agenda.utils.create_event_dict")
    def test_process_email_cli_success(
        self,
        mock_create_event_dict,
        mock_input,
        mock_json_loads,
        mock_write_file,
        mock_select_calendar,
        mock_module_rules,
        mock_get_emails_from_folder,
        mock_select_email_source,
        mock_select_api_source,
    ):
        args = self.Args(
            interactive=False,
            delete=True,
            source="gemini",
            verbose=False,
            destination="",
            text="",
        )
        mock_model = MagicMock()
        mock_model.generate_text.return_value = """```json
{"summary": "Test Event", "start": {"dateTime": "2024-01-01T10:00:00"}, "end": {"dateTime": "2024-01-01T11:00:00"}}
```"""
        mock_json_loads.return_value = {
            "summary": "Test Event",
            "start": {"dateTime": "2024-01-01T10:00:00"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }

        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "Label_0"}]
        mock_api_src.getPosts.return_value = ["post_id"]
        mock_api_src.getPostId.return_value = "post_id"
        mock_api_src.getPostDate.return_value = formatdate(
            timeval=datetime.datetime.now().timestamp(), localtime=True
        )
        mock_api_src.getPostTitle.return_value = "Test title"
        mock_api_src.getPostBody.return_value = "Test Body"

        mock_select_email_source.return_value = "test_source"
        mock_get_emails_from_folder.return_value = (mock_api_src, ["post_id"])

        mock_api_dst = MagicMock()
        mock_select_api_source.return_value = mock_api_dst
        mock_select_calendar.return_value = "primary"

        mock_rules = MagicMock()
        mock_rules.selectRule.side_effect = [["src_rule"], ["dst_rule"]]
        mock_rules.more.get.side_effect = [{"key": "src_value"}, {"key": "dst_value"}]
        mock_rules.readConfigSrc.side_effect = [mock_api_src, mock_api_dst]
        mock_module_rules.return_value = mock_rules
        mock_create_event_dict.return_value = {
            "summary": "",
            "location": "",
            "description": "",
            "start": {"dateTime": "", "timeZone": ""},
            "end": {"dateTime": "", "timeZone": ""},
            "recurrence": [],
        }

        process_email_cli(args, mock_model)

        mock_model.generate_text.assert_called_once()
        self.assertEqual(mock_write_file.call_count, 4)  # email, vcal, json, _times.json
        mock_select_calendar.assert_called_once()
        mock_api_dst.publishPost.assert_called_once()
        mock_api_src.modifyLabels.assert_called_once()

        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("builtins.print")
    def test_list_events_folder_with_posts(self, mock_print):
        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = True
        # Configure setPosts to set the return value for getPosts
        mock_api_src.setPosts.side_effect = lambda: setattr(
            mock_api_src, "getPosts", MagicMock(return_value=["post1", "post2"])
        )
        mock_api_src.getPostId.return_value = "post_id"
        mock_api_src.getPostDate.return_value = "post_date"
        mock_api_src.getPostTitle.return_value = "post_title"
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_events_folder(args, mock_api_src)
        mock_api_src.setPosts.assert_called_once()
        self.assertEqual(mock_print.call_count, 2)

    @patch("builtins.print")
    def test_list_events_folder_no_posts(self, mock_print):
        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = True
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_events_folder(args, mock_api_src)
        mock_api_src.setPosts.assert_called_once()
        mock_print.assert_not_called()

    @patch("manage_agenda.utils.select_email_source")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("builtins.print")
    def test_list_emails_folder_with_posts(
        self, mock_print, mock_get_emails, mock_select_email_source
    ):
        mock_api_src = MagicMock()
        mock_select_email_source.return_value = "test_source"
        mock_get_emails.return_value = (mock_api_src, ["post1", "post2"])
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_emails_folder(args)
        mock_select_email_source.assert_called_once_with(args)
        mock_get_emails.assert_called_once_with(args, "test_source")
        self.assertEqual(mock_print.call_count, 2)

    @patch("manage_agenda.utils.select_email_source")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("builtins.print")
    def test_list_emails_folder_no_posts(
        self, mock_print, mock_get_emails, mock_select_email_source
    ):
        mock_select_email_source.return_value = "test_source"
        mock_get_emails.return_value = (None, None)
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_emails_folder(args)
        mock_select_email_source.assert_called_once_with(args)
        mock_get_emails.assert_called_once_with(args, "test_source")
        mock_print.assert_not_called()


class TestUtils(unittest.TestCase):
    def test_extract_json(self):
        text = """Some text

        ```json
{"key": "value"}
        ```

more text"""
        expected_json = '{"key": "value"}'
        self.assertEqual(extract_json(text), expected_json)

    def test_process_event_data(self):
        event = {"description": "Original description"}
        content = "Email content"
        result = process_event_data(event, content)
        self.assertIn("Email content", result["description"])

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

    def test_create_event_dict(self):
        event_dict = create_event_dict()
        self.assertIsInstance(event_dict, dict)
        self.assertIn("summary", event_dict)
        self.assertIn("start", event_dict)

    @patch("manage_agenda.utils.select_from_list")
    def test_select_calendar(self, mock_select_from_list):
        mock_calendar_api = MagicMock()
        calendars = [{"summary": "Calendar1", "id": "id1", "accessRole": "owner"}]
        mock_calendar_api.getCalendarList.return_value = calendars
        mock_select_from_list.return_value = (0, "Calendar1")

        result = select_calendar(mock_calendar_api)

        mock_calendar_api.setCalendarList.assert_called_once()
        mock_select_from_list.assert_called_once()
        self.assertEqual(result, "id1")

    def test_safe_get(self):
        data = {"a": {"b": {"c": "value"}}}
        self.assertEqual(safe_get(data, ["a", "b", "c"]), "value")
        self.assertEqual(safe_get(data, ["a", "x", "c"]), "")
        self.assertEqual(safe_get(data, ["a", "b", "c", "d"]), "")

    @patch("click.prompt", return_value="0")
    @patch("os.popen")
    @patch("click.echo")
    @patch("click.echo_via_pager")
    def test_list_of_strings_numeric_selection(
        self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt
    ):
        mock_popen.return_value.read.return_value = "24 80"
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options), (0, "apple"))

    @patch("click.prompt", return_value="ban")
    @patch("os.popen")
    @patch("click.echo")
    @patch("click.echo_via_pager")
    def test_list_of_strings_substring_selection(
        self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt
    ):
        mock_popen.return_value.read.return_value = "24 80"
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options), (1, "banana"))

    @patch("click.prompt", return_value="")
    @patch("os.popen")
    @patch("click.echo")
    @patch("click.echo_via_pager")
    def test_list_of_strings_default_selection(
        self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt
    ):
        mock_popen.return_value.read.return_value = "24 80"
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options, default="banana"), (1, "banana"))

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_authorize_interactive(self, mock_module_rules):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        mock_rules = MagicMock()
        mock_module_rules.return_value = mock_rules
        with patch("manage_agenda.utils.input", return_value="gmail"):
            authorize(args)
        mock_rules.checkRules.assert_called_once()
        mock_rules.selectRuleInteractive.assert_called_once_with("gmail")

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_select_api_source_interactive(self, mock_module_rules):
        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        mock_rules = MagicMock()
        mock_module_rules.return_value = mock_rules
        select_api_source(args, "gmail")
        mock_rules.checkRules.assert_called_once()
        mock_rules.selectRuleInteractive.assert_called_once_with("gmail")

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_select_api_source_non_interactive(self, mock_module_rules):
        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["test_rule"]
        mock_rules.more.get.return_value = {"key": "value"}
        mock_module_rules.return_value = mock_rules
        select_api_source(args, "gmail")
        mock_rules.checkRules.assert_called_once()
        mock_rules.selectRule.assert_called_once_with("gmail", "")
        mock_rules.readConfigSrc.assert_called_once_with("", "test_rule", {"key": "value"})

    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    def tearDown(self):
        # Reset the rules cache after each test to ensure test isolation
        reset_cached_rules()

    @patch("manage_agenda.utils.input", return_value="l")
    @patch("manage_agenda.utils.OllamaClient")
    def test_select_llm_interactive_ollama(self, mock_ollama_client, mock_input):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)
        mock_ollama_client.assert_called_once()
        self.assertEqual(model, mock_ollama_client.return_value)

    @patch("manage_agenda.utils.input", return_value="m")
    @patch("manage_agenda.utils.MistralClient")
    def test_select_llm_interactive_mistral(self, mock_mistral_client, mock_input):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)
        mock_mistral_client.assert_called_once()
        self.assertEqual(model, mock_mistral_client.return_value)

    @patch("manage_agenda.utils.input", return_value="g")
    @patch("manage_agenda.utils.GeminiClient")
    def test_select_llm_interactive_gemini_explicit(self, mock_gemini_client, mock_input):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)
        mock_gemini_client.assert_called_once()
        self.assertEqual(model, mock_gemini_client.return_value)

    @patch("manage_agenda.utils.input", return_value="anything_else")
    @patch("manage_agenda.utils.GeminiClient")
    def test_select_llm_interactive_gemini_default(self, mock_gemini_client, mock_input):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)
        mock_gemini_client.assert_called_once()
        self.assertEqual(model, mock_gemini_client.return_value)

    @patch("manage_agenda.utils.OllamaClient")
    @patch("manage_agenda.utils.MistralClient")
    @patch("manage_agenda.utils.GeminiClient")
    def test_select_llm_non_interactive_always_gemini(
        self, mock_gemini_client, mock_mistral_client, mock_ollama_client
    ):
        # Because of a bug, non-interactive mode always uses Gemini

        # Source is 'gemini'
        args = self.Args(
            interactive=False,
            delete=False,
            source="gemini",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)
        mock_gemini_client.assert_called_with("gemini-2.5-flash")
        self.assertEqual(model, mock_gemini_client.return_value)

        # Source is 'ollama', but should be 'gemini'
        args = self.Args(
            interactive=False,
            delete=False,
            source="ollama",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)

        # Source is 'mistral', but should be 'gemini'
        args = self.Args(
            interactive=False,
            delete=False,
            source="mistral",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)

        # Source is 'invalid', but should be 'gemini'
        args = self.Args(
            interactive=False,
            delete=False,
            source="invalid",
            verbose=False,
            destination="",
            text="",
        )
        model = select_llm(args)

        # Check that only Gemini was called, 4 times.
        self.assertEqual(mock_gemini_client.call_count, 4)
        mock_mistral_client.assert_not_called()
        mock_ollama_client.assert_not_called()

    def test_print_first_10_lines_short(self):
        """Test print_first_10_lines with content shorter than 10 lines."""
        import io

        from manage_agenda.utils import print_first_10_lines

        content = "line1\nline2\nline3"
        captured_output = io.StringIO()
        sys.stdout = captured_output
        print_first_10_lines(content, "test")
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("line1", output)
        self.assertIn("line2", output)
        self.assertIn("line3", output)

    def test_print_first_10_lines_long(self):
        """Test print_first_10_lines with content longer than 10 lines."""
        import io
        import sys

        from manage_agenda.utils import print_first_10_lines

        content = "\n".join([f"line{i}" for i in range(20)])
        captured_output = io.StringIO()
        sys.stdout = captured_output
        print_first_10_lines(content)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("line0", output)
        self.assertIn("line9", output)
        self.assertNotIn("line10", output)

    @patch("manage_agenda.utils.select_from_list")
    def test_select_calendar_no_calendars(self, mock_select_from_list):
        """Test select_calendar when no calendars are found."""
        from manage_agenda.exceptions import CalendarError

        mock_calendar_api = MagicMock()
        mock_calendar_api.getCalendarList.return_value = []

        with self.assertRaises(CalendarError) as context:
            select_calendar(mock_calendar_api)

        self.assertIn("No calendars found", str(context.exception))

    @patch("manage_agenda.utils.select_from_list")
    def test_select_calendar_no_writable(self, mock_select_from_list):
        """Test select_calendar when no writable calendars exist."""
        from manage_agenda.exceptions import CalendarError

        mock_calendar_api = MagicMock()
        calendars = [{"summary": "Calendar1", "id": "id1", "accessRole": "reader"}]
        mock_calendar_api.getCalendarList.return_value = calendars

        with self.assertRaises(CalendarError) as context:
            select_calendar(mock_calendar_api)

        self.assertIn("No writable calendars", str(context.exception))

    @patch("manage_agenda.utils.format_time")
    def test_get_event_from_llm_success(self, mock_format_time):
        """Test get_event_from_llm with successful response."""
        from manage_agenda.utils import get_event_from_llm

        mock_format_time.return_value = "0h 0m 1.00s"
        mock_model = MagicMock()
        mock_model.generate_text.return_value = (
            '{"summary": "Test Event", "start": {"dateTime": "2024-01-01T10:00:00"}}'
        )

        prompt = "Create an event"
        event, vcal_json, elapsed_time = get_event_from_llm(mock_model, prompt, verbose=False)

        self.assertIsNotNone(event)
        self.assertEqual(event["summary"], "Test Event")
        self.assertIsInstance(elapsed_time, float)

    @patch("manage_agenda.utils.format_time")
    def test_get_event_from_llm_no_response(self, mock_format_time):
        """Test get_event_from_llm when LLM returns no response."""
        import io

        from manage_agenda.utils import get_event_from_llm

        mock_format_time.return_value = "0h 0m 1.00s"
        mock_model = MagicMock()
        mock_model.generate_text.return_value = ""

        captured_output = io.StringIO()
        sys.stdout = captured_output
        event, vcal_json, elapsed_time = get_event_from_llm(mock_model, "test", verbose=False)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("Failed to get response", output)

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

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_get_add_sources(self, mock_module_rules):
        """Test get_add_sources returns correct sources."""
        from manage_agenda.utils import get_add_sources

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        mock_rules = MagicMock()
        mock_rules.selectRule.side_effect = [["gmail1"], ["imap1"]]
        mock_module_rules.return_value = mock_rules

        sources = get_add_sources()

        self.assertIn("gmail1", sources)
        self.assertIn("imap1", sources)
        self.assertIn("Web (Enter URL)", sources)

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
        # The function finds from first { to last }
        self.assertIn('"key"', result)
        self.assertIn('"nested"', result)

    def test_get_post_datetime_and_diff_timestamp(self):
        """Test _get_post_datetime_and_diff with timestamp."""
        from manage_agenda.utils import _get_post_datetime_and_diff

        # Use a timestamp (milliseconds)
        timestamp = str(int(datetime.datetime.now().timestamp() * 1000))
        post_datetime, time_diff = _get_post_datetime_and_diff(timestamp)

        self.assertIsInstance(post_datetime, datetime.datetime)
        self.assertIsInstance(time_diff, datetime.timedelta)
        # Should be very recent (less than 1 day)
        self.assertLess(time_diff.days, 1)

    def test_get_post_datetime_and_diff_email_format(self):
        """Test _get_post_datetime_and_diff with email date format."""
        from email.utils import formatdate

        from manage_agenda.utils import _get_post_datetime_and_diff

        # Use email date format
        email_date = formatdate(timeval=datetime.datetime.now().timestamp(), localtime=True)
        post_datetime, time_diff = _get_post_datetime_and_diff(email_date)

        self.assertIsInstance(post_datetime, datetime.datetime)
        self.assertIsInstance(time_diff, datetime.timedelta)

    @patch("manage_agenda.utils.input", return_value="y")
    def test_delete_email_interactive_confirm(self, mock_input):
        """Test _delete_email with interactive confirmation."""
        from manage_agenda.utils import _delete_email

        args = Args(interactive=True, delete=False)
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getChannel.return_value = "test_folder"
        mock_api_src.getLabels.return_value = [{"id": "label_1"}]

        _delete_email(args, mock_api_src, "post123", "test_source")

        # Should call modifyLabels for gmail
        mock_api_src.modifyLabels.assert_called_once()

    def test_delete_email_non_interactive_no_delete(self):
        """Test _delete_email non-interactive without delete flag."""
        from manage_agenda.utils import _delete_email

        args = Args(interactive=False, delete=False)
        mock_api_src = MagicMock()

        _delete_email(args, mock_api_src, "post123", "test_source")

        # Should not delete anything
        mock_api_src.modifyLabels.assert_not_called()
        mock_api_src.deletePostId.assert_not_called()

    def test_delete_email_imap(self):
        """Test _delete_email with IMAP service."""
        from manage_agenda.utils import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"

        _delete_email(args, mock_api_src, "post123", "test_source")

        # Should call deletePostId for IMAP
        mock_api_src.deletePostId.assert_called_once_with("post123")

    def test_delete_email_retry(self):
        """Test _delete_email with connection error and retry."""
        from manage_agenda.utils import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.deletePostId.side_effect = [Exception("Connection error"), None]

        with patch("manage_agenda.utils.moduleRules.moduleRules") as mock_module_rules:
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.return_value = mock_rules

            _delete_email(args, mock_api_src, "post123", "test_source")

            # deletePostId is called once on the old object
            self.assertEqual(mock_api_src.deletePostId.call_count, 1)
            # The second call is on the new api_src object
            mock_new_api_src.deletePostId.assert_called_once_with("post123")

    def test_delete_email_retry_failure(self):
        """Test _delete_email with connection error and all retries fail."""
        from manage_agenda.utils import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"
        # Simulate two failures (original + retry)
        mock_api_src.deletePostId.side_effect = Exception("Connection error 1") # Only for the first call

        with patch("manage_agenda.utils.moduleRules.moduleRules") as mock_module_rules, \
             patch("manage_agenda.utils.logging.error") as mock_logging_error:
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_new_api_src.deletePostId.side_effect = Exception("Connection error 2") # For the retry call
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.return_value = mock_rules

            _delete_email(args, mock_api_src, "post123", "test_source")

            # deletePostId is called once on the old object
            self.assertEqual(mock_api_src.deletePostId.call_count, 1)
            # deletePostId is called once on the new api_src object
            self.assertEqual(mock_new_api_src.deletePostId.call_count, 1)
            
            # Check that the error message was logged
            mock_logging_error.assert_called_once_with("Could not delete email post123 after 2 attempts: Connection error 2")



    def test_is_email_too_old_recent(self):
        """Test _is_email_too_old with recent email."""
        from manage_agenda.utils import _is_post_too_old

        args = Args(interactive=False, verbose=False)
        time_diff = datetime.timedelta(days=3)

        result = _is_post_too_old(args, time_diff)

        self.assertFalse(result)

    def test_is_email_too_old_old_non_interactive(self):
        """Test _is_email_too_old with old email, non-interactive."""
        from manage_agenda.utils import _is_post_too_old

        args = Args(interactive=False, verbose=True)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertTrue(result)

    @patch("manage_agenda.utils.input", return_value="n")
    def test_is_email_too_old_interactive_reject(self, mock_input):
        """Test _is_email_too_old with interactive rejection."""
        from manage_agenda.utils import _is_post_too_old

        args = Args(interactive=True, verbose=False)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertTrue(result)

    @patch("manage_agenda.utils.input", return_value="y")
    def test_is_email_too_old_interactive_accept(self, mock_input):
        """Test _is_email_too_old with interactive acceptance."""
        from manage_agenda.utils import _is_post_too_old

        args = Args(interactive=True, verbose=False)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertFalse(result)

    def test_create_llm_prompt(self):
        """Test _create_llm_prompt generates correct prompt."""
        from manage_agenda.utils import _create_llm_prompt

        event = create_event_dict()
        content = "Meeting about project X on Monday at 3pm"
        ref_date = datetime.datetime(2024, 1, 15, 10, 0, 0)

        prompt = _create_llm_prompt(event, content, ref_date)

        self.assertIn("Meeting about project X", prompt)
        self.assertIn("JSON", prompt)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_select_email_source_interactive(self, mock_module_rules):
        """Test select_email_source in interactive mode."""
        from manage_agenda.utils import select_email_source

        args = Args(interactive=True)
        mock_rules = MagicMock()
        mock_rules.selectRule.side_effect = [["gmail1"], ["imap1"]]
        mock_module_rules.return_value = mock_rules

        with patch("manage_agenda.utils.select_from_list", return_value=(0, "gmail1")):
            result = select_email_source(args)
            self.assertEqual(result, 0)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_select_email_source_non_interactive(self, mock_module_rules):
        """Test select_email_source in non-interactive mode."""
        from manage_agenda.utils import select_email_source

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False)
        mock_rules = MagicMock()
        mock_rules.selectRule.side_effect = [["gmail1"], ["imap1"]]
        mock_module_rules.return_value = mock_rules

        result = select_email_source(args)

        self.assertEqual(result, "gmail1")

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_list_events_folder_with_posts(self, mock_module_rules):
        """Test list_events_folder with posts."""
        import io

        from manage_agenda.utils import list_events_folder

        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.getPosts.return_value = [
            {"id": "1", "date": "2024-01-01", "title": "Event 1"},
            {"id": "2", "date": "2024-01-02", "title": "Event 2"},
        ]
        mock_api_src.getPostId.side_effect = lambda post: post["id"]
        mock_api_src.getPostDate.side_effect = lambda post: post["date"]
        mock_api_src.getPostTitle.side_effect = lambda post: post["title"]

        captured_output = io.StringIO()
        sys.stdout = captured_output
        list_events_folder(args, mock_api_src)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("Event 1", output)
        self.assertIn("Event 2", output)
        mock_api_src.setPosts.assert_called_once()

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_list_events_folder_no_client(self, mock_module_rules):
        """Test list_events_folder when client is not available."""
        import io

        from manage_agenda.utils import list_events_folder

        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = None

        captured_output = io.StringIO()
        sys.stdout = captured_output
        list_events_folder(args, mock_api_src)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("Some problem with the account", output)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_get_emails_from_folder_success(self, mock_module_rules):
        """Test _get_emails_from_folder with successful retrieval."""
        from manage_agenda.utils import _get_emails_from_folder

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.more.get.return_value = {"key": "value"}

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1", "name": "zAgenda"}]
        mock_api_src.getPosts.return_value = [{"id": "1"}, {"id": "2"}]

        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        api_src, posts = _get_emails_from_folder(args, "gmail1")

        self.assertIsNotNone(api_src)
        self.assertIsNotNone(posts)
        self.assertEqual(len(posts), 2)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_get_emails_from_folder_no_client(self, mock_module_rules):
        """Test _get_emails_from_folder when client fails."""
        import io

        from manage_agenda.utils import _get_emails_from_folder

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.more.get.return_value = {}

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = None

        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        captured_output = io.StringIO()
        sys.stdout = captured_output
        api_src, posts = _get_emails_from_folder(args, "gmail1")
        sys.stdout = sys.__stdout__

        self.assertIsNone(api_src)
        self.assertIsNone(posts)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_get_emails_from_folder_no_label(self, mock_module_rules):
        """Test _get_emails_from_folder when label doesn't exist."""
        from manage_agenda.utils import _get_emails_from_folder

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.more.get.return_value = {}

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.getLabels.return_value = []

        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        api_src, posts = _get_emails_from_folder(args, "imap1")

        self.assertIsNotNone(api_src)
        self.assertIsNone(posts)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_get_emails_from_folder_no_posts(self, mock_module_rules):
        """Test _get_emails_from_folder when no posts found."""
        from manage_agenda.utils import _get_emails_from_folder

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.more.get.return_value = {}

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1"}]
        mock_api_src.getPosts.return_value = []

        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        api_src, posts = _get_emails_from_folder(args, "gmail1")

        self.assertIsNotNone(api_src)
        self.assertIsNone(posts)

    @patch("manage_agenda.utils.select_email_source", return_value="gmail1")
    @patch("manage_agenda.utils._get_emails_from_folder")
    def test_list_emails_folder_with_posts(self, mock_get_emails, mock_select_source):
        """Test list_emails_folder with posts."""
        import io

        from manage_agenda.utils import list_emails_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getPostTitle.side_effect = ["Email 1", "Email 2"]
        mock_get_emails.return_value = (mock_api_src, [{"id": "1"}, {"id": "2"}])

        captured_output = io.StringIO()
        sys.stdout = captured_output
        list_emails_folder(args)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("Email 1", output)
        self.assertIn("Email 2", output)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_authorize_success(self, mock_module_rules):
        """Test authorize function."""
        from manage_agenda.utils import authorize

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["source1"]
        mock_rules.more.get.return_value = {"key": "value"}

        mock_api_src = MagicMock()
        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        result = authorize(args)

        self.assertIsNotNone(result)
        self.assertEqual(result, mock_api_src)

    @patch("manage_agenda.utils.moduleRules.moduleRules")
    def test_authorize_no_services(self, mock_module_rules):
        """Test authorize when no services configured."""
        from manage_agenda.utils import authorize

        # Reset cache to ensure fresh instance for this test
        reset_cached_rules()

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = []
        mock_module_rules.return_value = mock_rules

        result = authorize(args)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

    @patch("manage_agenda.utils.select_api_source")
    @patch("manage_agenda.utils.select_calendar", return_value="calendar1")
    @patch("builtins.input", side_effect=["meeting", "0", "calendar2"])
    def test_copy_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test copy_events_cli basic flow."""
        from manage_agenda.utils import copy_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        # Mock events list
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
        mock_select_api.return_value = mock_api

        copy_events_cli(args)

        # Verify event was inserted
        mock_client.events().insert.assert_called()

    @patch("manage_agenda.utils.select_api_source")
    @patch("manage_agenda.utils.select_calendar", return_value="calendar1")
    @patch("builtins.input", return_value="0")
    def test_delete_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test delete_events_cli basic flow."""
        from manage_agenda.utils import delete_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        # Mock events list
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
        mock_select_api.return_value = mock_api

        delete_events_cli(args)

        # Verify event was deleted
        mock_client.events().delete.assert_called()

    @patch("manage_agenda.utils.select_api_source")
    @patch("manage_agenda.utils.select_calendar", return_value="calendar1")
    @patch("builtins.input", side_effect=["0", "calendar2"])
    def test_move_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test move_events_cli basic flow."""
        from manage_agenda.utils import move_events_cli

        args = Args(
            interactive=True, source=None, destination=None, text=None, delete=False, verbose=False
        )

        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_api.getClient.return_value = mock_client

        # Mock events list
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
        mock_select_api.return_value = mock_api

        move_events_cli(args)

        # Verify event was moved
        mock_client.events().move.assert_called()
