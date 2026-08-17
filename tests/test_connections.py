import unittest
from collections import namedtuple
from unittest.mock import MagicMock, patch

from socialModules.configMod import safe_get, select_from_list

from manage_agenda.connections import authorize, select_api, select_calendar
from manage_agenda.sources import Args


class TestConnections(unittest.TestCase):
    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.connections.select_from_list")
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

    @patch("manage_agenda.connections.moduleRules")
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
        with patch("builtins.input", return_value="gmail"):
            authorize(args)
        mock_module_rules.from_config.assert_called_once()
        mock_rules.selectRuleInteractive.assert_called_once_with("gmail")

    @patch("manage_agenda.connections.moduleRules")
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

    @patch("manage_agenda.connections.moduleRules")
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

    @patch("manage_agenda.connections.select_from_list")
    def test_select_calendar_no_calendars(self, mock_select_from_list):
        """Test select_calendar when no calendars are found."""
        from manage_agenda.exceptions import CalendarError

        mock_calendar_api = MagicMock()
        mock_calendar_api.getCalendarList.return_value = []

        with self.assertRaises(CalendarError) as context:
            select_calendar(mock_calendar_api)

        self.assertIn("No calendars found", str(context.exception))

    @patch("manage_agenda.connections.select_from_list")
    def test_select_calendar_no_writable(self, mock_select_from_list):
        """Test select_calendar when no writable calendars exist."""
        from manage_agenda.exceptions import CalendarError

        mock_calendar_api = MagicMock()
        calendars = [{"summary": "Calendar1", "id": "id1", "accessRole": "reader"}]
        mock_calendar_api.getCalendarList.return_value = calendars

        with self.assertRaises(CalendarError) as context:
            select_calendar(mock_calendar_api)

        self.assertIn("No writable calendars", str(context.exception))

    @patch("manage_agenda.connections.moduleRules")
    def test_select_api_email_interactive(self, mock_module_rules):
        """Test select_api with email type in interactive mode."""
        args = Args(interactive=True)
        mock_rules = MagicMock()
        mock_module_rules.from_config.return_value = mock_rules

        result = select_api(args, "email")
        self.assertIsNotNone(result)
        mock_rules.selectRuleInteractive.assert_called_once()

    @patch("manage_agenda.connections.moduleRules")
    def test_select_api_email_non_interactive(self, mock_module_rules):
        """Test select_api with email type in non-interactive mode."""
        args = Args(interactive=False)
        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["gmail1"]
        mock_rules.more.get.return_value = {"key": "value"}
        mock_module_rules.from_config.return_value = mock_rules

        result = select_api(args, "email", rules=mock_rules)

        self.assertIsNotNone(result)
        mock_rules.selectRule.assert_called_once()
        mock_rules.readConfigSrc.assert_called_once()

    @patch("manage_agenda.connections.moduleRules")
    def test_authorize_success(self, mock_module_rules):
        """Test authorize function."""
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

    @patch("manage_agenda.connections.moduleRules")
    def test_authorize_no_services(self, mock_module_rules):
        """Test authorize when no services configured."""
        args = Args(interactive=False, delete=False, verbose=False)

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = []
        mock_module_rules.return_value = mock_rules

        result = authorize(args, rules=mock_rules)

        self.assertIsNone(result)
