import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import datetime
import sys

from socialModules.configMod import select_from_list

# from manage_agenda.utils_base import select_from_list
from manage_agenda.utils_llm import LLMClient
from manage_agenda.utils import (
    extract_json,
    process_event_data,
    adjust_event_times,
    create_event_dict,
    select_calendar,
    safe_get,
    # select_from_list,
)


class TestUtils(unittest.TestCase):
    def test_extract_json(self):
        text = """Some text

        ```json\n{\"key\": \"value\"}\n
        ```

more text"""
        expected_json = '{"key": "value"}'
        self.assertEqual(extract_json(text), expected_json)

    def test_process_event_data(self):
        event = {"description": "Original description"}
        content = "Email content"
        result = process_event_data(event, content)
        self.assertIn("Email content", result["description"])
        self.assertEqual(result["attendees"], [])

    def test_adjust_event_times_both_present(self):
        event = {
            "start": {"dateTime": "2024-01-01T10:00:00"},
            "end": {"dateTime": "2024-01-01T11:00:00"},
        }
        result = adjust_event_times(event)
        self.assertEqual(result["start"]["dateTime"], "2024-01-01T10:00:00")
        self.assertEqual(result["end"]["dateTime"], "2024-01-01T11:00:00")
        self.assertEqual(result["start"]["timeZone"], "Europe/Madrid")
        self.assertEqual(result["end"]["timeZone"], "Europe/Madrid")

    def test_adjust_event_times_start_missing(self):
        event = {"end": {"dateTime": "2024-01-01T11:00:00"}}
        result = adjust_event_times(event)
        self.assertEqual(result["start"]["dateTime"], "2024-01-01T11:00:00")
        self.assertEqual(result["start"]["timeZone"], "Europe/Madrid")

    def test_adjust_event_times_end_missing(self):
        event = {"start": {"dateTime": "2024-01-01T10:00:00"}}
        result = adjust_event_times(event)
        self.assertEqual(result["end"]["dateTime"], "2024-01-01T10:00:00")
        self.assertEqual(result["end"]["timeZone"], "Europe/Madrid")

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

    # @patch("manage_agenda.utils.input", return_value="0")
    # def test_select_message(self, mock_input):
    #     mock_message_src = MagicMock()
    #     mock_message_src.setPosts.return_value = None
    #     mock_message_src.getPosts.return_value = ["message1", "message2"]
    #     mock_message_src.getPostFrom.return_value = "sender"
    #     mock_message_src.getPostTitle.return_value = "subject"
    #     result = select_message(mock_message_src)
    #     self.assertEqual(result, "message1")

    # @patch("manage_agenda.utils.select_message")
    # def test_select_message_folder(self, mock_select_message):
    #     mock_message_src = MagicMock()
    #     mock_message_src.getChannel.return_value = "INBOX"
    #     mock_select_message.return_value = "selected_message"
    #     result = select_message_folder(mock_message_src, folder="INBOX")
    #     mock_message_src.setChannel.assert_called_once_with("INBOX")
    #     mock_select_message.assert_called_once()
    #     self.assertEqual(result, "selected_message")

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

    @patch('click.prompt', return_value='0')  # Simula la entrada del usuario "0"
    @patch('os.popen')
    @patch('click.echo')
    @patch('click.echo_via_pager')
    def test_list_of_strings_numeric_selection(self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt):
        mock_popen.return_value.read.return_value = "24 80" # Simulamos el tamaño de la terminal
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options), (0, "apple"))
    
    @patch('click.prompt', return_value='ban')
    @patch('os.popen')
    @patch('click.echo')
    @patch('click.echo_via_pager')
    def test_list_of_strings_substring_selection(self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt):
        mock_popen.return_value.read.return_value = "24 80"
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options), (1, "banana"))
    
    @patch('click.prompt', return_value='')
    @patch('os.popen')
    @patch('click.echo')
    @patch('click.echo_via_pager')
    def test_list_of_strings_default_selection(self, mock_echo_via_pager, mock_echo, mock_popen, mock_prompt):
        mock_popen.return_value.read.return_value = "24 80"
        options = ["apple", "banana", "cherry"]
        self.assertEqual(select_from_list(options, default="banana"), (1, "banana"))
