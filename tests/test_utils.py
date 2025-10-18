import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import datetime
import sys
from collections import namedtuple
from email.utils import formatdate

from socialModules.configMod import select_from_list

# from manage_agenda.utils_base import select_from_list
from manage_agenda.utils_llm import LLMClient, OllamaClient, GeminiClient, MistralClient
from manage_agenda.utils import (
    extract_json,
    process_event_data,
    adjust_event_times,
    create_event_dict,
    select_calendar,
    safe_get,
    select_llm,
    Args,
    authorize,
    select_api_source,
    list_events_folder,
    list_emails_folder,
    process_email_cli,
)


class TestProcessEmailCli(unittest.TestCase):
    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

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

        mock_api_dst = MagicMock()
        mock_select_calendar.return_value = "primary"

        mock_rules = MagicMock()
        mock_rules.selectRule.side_effect = [["src_rule"], ["dst_rule"]]
        mock_rules.more.get.side_effect = [{"key": "src_value"}, {"key": "dst_value"}]
        mock_rules.readConfigSrc.side_effect = [mock_api_src, mock_api_dst]
        mock_module_rules.return_value = mock_rules
        mock_create_event_dict.return_value = {"summary": "", "location": "", "description": "", "start": {"dateTime": "", "timeZone": ""}, "end": {"dateTime": "", "timeZone": ""}, "recurrence": []}

        process_email_cli(args, mock_model)

        mock_model.generate_text.assert_called_once()
        self.assertEqual(
            mock_write_file.call_count, 4
        )  # email, vcal, json, _times.json
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

    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("builtins.print")
    def test_list_emails_folder_with_posts(self, mock_print, mock_get_emails):
        mock_api_src = MagicMock()
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
        mock_get_emails.assert_called_once_with(args)
        self.assertEqual(mock_print.call_count, 2)

    @patch("manage_agenda.utils._get_emails_from_folder")
    @patch("builtins.print")
    def test_list_emails_folder_no_posts(self, mock_print, mock_get_emails):
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
        mock_get_emails.assert_called_once_with(args)
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
        mock_rules.readConfigSrc.assert_called_once_with(
            "", "test_rule", {"key": "value"}
        )

    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

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
    def test_select_llm_interactive_gemini_explicit(
        self, mock_gemini_client, mock_input
    ):
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
    def test_select_llm_interactive_gemini_default(
        self, mock_gemini_client, mock_input
    ):
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
        mock_gemini_client.assert_called_with("gemini-1.5-flash-latest")
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
