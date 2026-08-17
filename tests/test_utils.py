import datetime
import sys
import unittest
from collections import namedtuple
from email.utils import formatdate
from unittest.mock import MagicMock, patch

from socialModules.configMod import select_from_list

from manage_agenda.utils import (
    Args,
    add_message_to_event_description,
    authorize,
    create_event_dict,
    extract_json,
    list_folder,
    process_email_cli,
    safe_get,
    select_api,
    select_calendar,
)
from manage_agenda.utils_events import adjust_event_times
from manage_agenda.utils_llm import select_llm

# from manage_agenda.utils_base import select_from_list


class TestProcessEmailCli(unittest.TestCase):
    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.utils.select_api")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("manage_agenda.utils.moduleRules")
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
        mock_select_api,
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

        mock_get_emails_from_folder.return_value = ["post_id"]

        mock_api_dst = MagicMock()
        mock_select_api.side_effect = [mock_api_src, mock_api_dst]
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

        self.assertEqual(mock_model.generate_text.call_count, 2)
        self.assertEqual(mock_write_file.call_count, 10)
        mock_select_calendar.assert_called_once()
        mock_api_dst.publishPost.assert_called_once()
        mock_api_src.modifyLabels.assert_called_once()

        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_events_from_calendar")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gcalendar_folder_with_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        mock_api_src = MagicMock()
        events = ["post1", "post2"]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = events
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gcalendar")
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gcalendar", title="Select calendar account"
        )
        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, events)

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_events_from_calendar")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gcalendar_folder_without_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = None
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gcalendar")
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gcalendar", title="Select calendar account"
        )
        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gmail_folder_with_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = ["post1", "post2"]
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gmail")
        mock_module_rules.from_config.assert_called_once()
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, ["post1", "post2"])

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gmail_folder_without_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = None
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gmail")
        mock_module_rules.from_config.assert_called_once()
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)

    @patch("manage_agenda.utils_events.select_events_by_user_input", return_value=[])
    @patch("manage_agenda.utils_events.display_posts")
    @patch("manage_agenda.utils_events.select_calendar", return_value="calendar-id")
    @patch("manage_agenda.utils_events.select_api")
    def test_update_event_status_uses_calendar_posts(
        self,
        mock_select_api,
        mock_select_calendar,
        mock_display_posts,
        mock_select_events,
    ):
        from manage_agenda.utils_events import update_event_status_cli

        args = Args(interactive=False, output="", text="")
        api_cal = MagicMock()
        events = [{"summary": "Event", "transparency": "opaque"}]
        api_cal.getPosts.return_value = events
        api_cal.getPostTitle.return_value = "Event"
        mock_select_api.return_value = api_cal

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


class TestUtils(unittest.TestCase):
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

    @patch("manage_agenda.utils.moduleRules")
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
        mock_module_rules.from_config.return_value = mock_rules
        with patch("manage_agenda.utils.input", return_value="gmail"):
            authorize(args)
        mock_module_rules.from_config.assert_called_once()
        mock_rules.selectRuleInteractive.assert_called_once_with("gmail")

    @patch("manage_agenda.utils.moduleRules")
    def test_select_api_interactive(self, mock_module_rules):
        args = self.Args(
            interactive=True,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        mock_rules = MagicMock()
        select_api(args, "gmail", rules=mock_rules)
        mock_rules.selectRuleInteractive.assert_called_once_with(["gmail"], title="")

    @patch("manage_agenda.utils.moduleRules")
    def test_select_api_non_interactive(self, mock_module_rules):
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
        select_api(args, "gmail", rules=mock_rules)
        mock_rules.selectRule.assert_called_once_with(["gmail"], "")
        mock_rules.readConfigSrc.assert_called_once_with("", "test_rule", {"key": "value"})

    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "ollama"))
    @patch("manage_agenda.utils_llm.OllamaClient")
    def test_select_llm_interactive_ollama(self, mock_ollama_client, mock_sfl):
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

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(2, "mistral"))
    @patch("manage_agenda.utils_llm.MistralClient")
    def test_select_llm_interactive_mistral(self, mock_mistral_client, mock_sfl):
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

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(1, "gemini"))
    @patch("manage_agenda.utils_llm.GeminiClient")
    def test_select_llm_interactive_gemini_explicit(self, mock_gemini_client, mock_sfl):
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

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(1, "gemini"))
    @patch("manage_agenda.utils_llm.GeminiClient")
    def test_select_llm_interactive_gemini_default(self, mock_gemini_client, mock_sfl):
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

    @patch("manage_agenda.utils_llm.OllamaClient")
    @patch("manage_agenda.utils_llm.MistralClient")
    @patch("manage_agenda.utils_llm.GeminiClient")
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
        event, vcal_json, elapsed_time = get_event_from_llm(
            mock_model, prompt, post_id="test_post_123", verbose=False
        )

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
        event, vcal_json, elapsed_time = get_event_from_llm(
            mock_model, "test", post_id="test_post_123", verbose=False
        )
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

    @patch("manage_agenda.utils.moduleRules")
    def test_get_add_sources(self, mock_module_rules):
        """Test get_add_sources returns correct sources."""
        from manage_agenda.utils import get_add_sources

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["gmail1", "imap1"]
        mock_module_rules.from_config.return_value = mock_rules

        sources = get_add_sources(rules=mock_rules)

        print(f"Sources: {sources}")
        self.assertIn("gmail1", sources[0])
        self.assertIn("imap1", sources[0])
        self.assertIn("web", str(sources[1]))
        self.assertIn("http", str(sources[1]))
        self.assertIn(("text", "set", "(enter filenames or leave empty)"), sources[1])

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

        with patch("manage_agenda.utils.moduleRules") as mock_module_rules:
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.from_config.return_value = mock_rules

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
        mock_api_src.deletePostId.side_effect = Exception(
            "Connection error 1"
        )  # Only for the first call

        with (
            patch("manage_agenda.utils.moduleRules") as mock_module_rules,
            patch("manage_agenda.utils.logging.error") as mock_logging_error,
        ):
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_new_api_src.deletePostId.side_effect = Exception(
                "Connection error 2"
            )  # For the retry call
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.from_config.return_value = mock_rules

            _delete_email(args, mock_api_src, "post123", "test_source")

            # deletePostId is called once on the old object
            self.assertEqual(mock_api_src.deletePostId.call_count, 1)
            # deletePostId is called once on the new api_src object
            self.assertEqual(mock_new_api_src.deletePostId.call_count, 1)

            # Check that the error message was logged
            mock_logging_error.assert_called_once_with(
                "Could not delete email post123 after 2 attempts: Connection error 2"
            )

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

    @patch("manage_agenda.utils.moduleRules")
    def test_select_api_email_interactive(self, mock_module_rules):
        """Test select_api with email type in interactive mode."""
        from manage_agenda.utils import select_api

        args = Args(interactive=True)
        mock_rules = MagicMock()
        mock_module_rules.from_config.return_value = mock_rules

        result = select_api(args, "email")
        self.assertIsNotNone(result)
        mock_rules.selectRuleInteractive.assert_called_once()

    @patch("manage_agenda.utils.moduleRules")
    def test_select_api_email_non_interactive(self, mock_module_rules):
        """Test select_api with email type in non-interactive mode."""
        from manage_agenda.utils import select_api

        args = Args(interactive=False)
        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["gmail1"]
        mock_rules.more.get.return_value = {"key": "value"}
        mock_module_rules.from_config.return_value = mock_rules

        result = select_api(args, "email", rules=mock_rules)

        self.assertIsNotNone(result)
        mock_rules.selectRule.assert_called_once()
        mock_rules.readConfigSrc.assert_called_once()

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_events_from_calendar")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gcalendar_folder_with_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        """Test listing a calendar folder with posts."""
        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        events = [
            {"id": "1", "date": "2024-01-01", "title": "Event 1"},
            {"id": "2", "date": "2024-01-02", "title": "Event 2"},
        ]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = events

        list_folder(args, "gcalendar")

        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, events)

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_events_from_calendar")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gcalendar_folder_without_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        """Test listing a calendar folder when no events are found."""
        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = None

        list_folder(args, "gcalendar")

        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)

    def test_get_emails_from_folder_success(self):
        """Test _get_emails_from_folder with successful retrieval."""
        from manage_agenda.utils import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1", "name": "zAgenda"}]
        mock_api_src.getPosts.return_value = [{"id": "1"}, {"id": "2"}]

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertIsNotNone(posts)
        self.assertEqual(len(posts), 2)

    def test_get_emails_from_folder_no_label(self):
        """Test _get_emails_from_folder when the label does not exist."""
        import io

        from manage_agenda.utils import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = []

        captured_output = io.StringIO()
        sys.stdout = captured_output
        posts = _get_emails_from_folder(args, mock_api_src)
        sys.stdout = sys.__stdout__

        self.assertIsNone(posts)

    def test_get_emails_from_folder_no_imap_label(self):
        """Test _get_emails_from_folder when the IMAP label does not exist."""
        from manage_agenda.utils import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.getLabels.return_value = []

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertIsNone(posts)

    def test_get_emails_from_folder_no_posts(self):
        """Test _get_emails_from_folder when no posts found."""
        from manage_agenda.utils import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1"}]
        mock_api_src.getPosts.return_value = []

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertEqual(posts, [])

    @patch("manage_agenda.utils.display_posts")
    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("manage_agenda.utils.moduleRules")
    def test_list_gmail_folder_with_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        """Test listing a Gmail folder with posts."""

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        posts = [{"id": "1"}, {"id": "2"}]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = posts

        list_folder(args, "gmail")

        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, posts)

    @patch("manage_agenda.utils.moduleRules")
    def test_authorize_success(self, mock_module_rules):
        """Test authorize function."""
        from manage_agenda.utils import authorize

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["source1"]
        mock_rules.more.get.return_value = {"key": "value"}

        mock_api_src = MagicMock()
        mock_rules.readConfigSrc.return_value = mock_api_src
        mock_module_rules.return_value = mock_rules

        result = authorize(args, rules=mock_rules)

        self.assertIsNotNone(result)
        self.assertEqual(result, mock_api_src)

    @patch("manage_agenda.utils.moduleRules")
    def test_authorize_no_services(self, mock_module_rules):
        """Test authorize when no services configured."""
        from manage_agenda.utils import authorize

        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = []
        mock_module_rules.return_value = mock_rules

        result = authorize(args, rules=mock_rules)

        self.assertIsNone(result)

    @patch("manage_agenda.utils_events.select_api")
    @patch("manage_agenda.utils_events.select_calendar", return_value="calendar1")
    @patch("builtins.input", side_effect=["meeting", "0", "calendar2"])
    def test_copy_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test copy_events_cli basic flow."""
        from manage_agenda.utils_events import copy_events_cli

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
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_api.return_value = mock_api

        copy_events_cli(args)

        # Verify event was inserted
        mock_client.events().insert.assert_called()

    @patch("manage_agenda.utils_events.select_api")
    @patch("manage_agenda.utils_events.select_calendar", return_value="calendar1")
    @patch("builtins.input", side_effect=["", "0"])
    def test_delete_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test delete_events_cli basic flow."""
        from manage_agenda.utils_events import delete_events_cli

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
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_api.return_value = mock_api

        delete_events_cli(args)

        # Verify event was deleted
        mock_client.events().delete.assert_called()

    @patch("manage_agenda.utils_events.select_api")
    @patch("manage_agenda.utils_events.select_calendar", return_value="calendar1")
    @patch("builtins.input", side_effect=["", "0", "calendar2"])
    def test_move_events_cli_basic(self, mock_input, mock_select_cal, mock_select_api):
        """Test move_events_cli basic flow."""
        from manage_agenda.utils_events import move_events_cli

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
        mock_api.getPosts.return_value = mock_events["items"]
        mock_select_api.return_value = mock_api

        move_events_cli(args)

        # Verify event was moved (via insert then delete)
        mock_client.events().insert.assert_called()
        mock_client.events().delete.assert_called()

    @patch("manage_agenda.utils.get_event_from_llm")
    @patch("manage_agenda.utils.select_api")
    @patch("manage_agenda.utils.select_calendar")
    @patch("manage_agenda.utils.write_file")
    @patch("manage_agenda.utils_events._validate_event_dates_interactive")
    def test_process_event_with_llm_and_calendar_multiple_events(
        self,
        mock_interactive_confirmation,
        mock_write_file,
        mock_select_calendar,
        mock_select_api,
        mock_get_event_from_llm,
    ):
        """Test _process_event_with_llm_and_calendar when LLM returns a tuple of events."""
        from manage_agenda.utils import Args, _process_event_with_llm_and_calendar

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

        # get_event_from_llm returns (event, vcal_json, elapsed_time)
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

        # Check write_file calls for suffix index files: _1.vcal, _1.json, _1_times.json, _2.vcal, ...
        # (each event writes 3 files)
        self.assertEqual(mock_write_file.call_count, 8)

        # Verify publishPost was called for both events
        self.assertEqual(mock_api_dst.publishPost.call_count, 2)

    @patch("manage_agenda.utils._extract_event_with_llm_retry")
    @patch("manage_agenda.utils.select_api")
    @patch("manage_agenda.utils.select_calendar")
    @patch("manage_agenda.utils.write_file")
    @patch("manage_agenda.utils_events._validate_event_dates_interactive")
    def test_process_event_with_llm_and_calendar_file_output(
        self,
        mock_interactive_confirmation,
        mock_write_file,
        mock_select_calendar,
        mock_select_api,
        mock_extract_event_with_llm_retry,
    ):
        """Test _process_event_with_llm_and_calendar with file output option."""
        from manage_agenda.utils import Args, _process_event_with_llm_and_calendar

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

        # _extract_event_with_llm_retry returns (event, vcal_json, elapsed_time, extraction_success, need_restart, need_another_ai)
        # event is always a list (enforced in _extract_event_with_llm_retry)
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

        # Verify select_api, select_calendar, and publishPost were not called
        mock_select_api.assert_not_called()
        mock_select_calendar.assert_not_called()

        # Verify file write was called
        mock_write_file.assert_called()


if __name__ == "__main__":
    unittest.main()
