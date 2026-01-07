import unittest
from collections import namedtuple
from unittest.mock import MagicMock, patch

from click.testing import CliRunner


class TestCliCommands(unittest.TestCase):

    # Class-level patchers
    mock_module_rules_patcher = patch("manage_agenda.utils.moduleRules.moduleRules")
    mock_select_from_list_patcher = patch("manage_agenda.cli.select_from_list")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Start class-level patchers
        cls.mock_module_rules_class = cls.mock_module_rules_patcher.start()
        cls.mock_select_from_list_class = cls.mock_select_from_list_patcher.start()

        # Configure class-level mocks
        cls.mock_rules_instance_class = MagicMock()
        cls.mock_module_rules_class.return_value = cls.mock_rules_instance_class
        cls.mock_rules_instance_class.checkRules.return_value = None
        cls.mock_rules_instance_class.selectRule.side_effect = [["gmail1"], ["imap1"]]

        cls.mock_select_from_list_class.return_value = (0, "default_selection") # Default, can be overridden per test

    @classmethod
    def tearDownClass(cls):
        # Stop class-level patchers
        cls.mock_module_rules_patcher.stop()
        cls.mock_select_from_list_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        from manage_agenda import cli

        self.cli = cli
        self.llm_name = "gemini"
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )
        self.runner = CliRunner()

        # Access class-level mocks via self
        self.mock_module_rules = self.mock_module_rules_class
        self.mock_select_from_list = self.mock_select_from_list_class
        self.mock_rules_instance = self.mock_rules_instance_class


        # Individual patches that apply per test method
        self.mock_get_add_sources_patcher = patch("manage_agenda.cli.get_add_sources")
        self.mock_get_add_sources = self.mock_get_add_sources_patcher.start()
        self.mock_get_add_sources.return_value = ["gmail1", "imap1", "Web (Enter URL)"]

        self.mock_select_llm_patcher = patch("manage_agenda.cli.select_llm")
        self.mock_select_llm = self.mock_select_llm_patcher.start()
        self.mock_llm = MagicMock()
        self.mock_select_llm.return_value = self.mock_llm

        self.mock_process_email_cli_patcher = patch("manage_agenda.cli.process_email_cli")
        self.mock_process_email_cli = self.mock_process_email_cli_patcher.start()
        self.mock_process_email_cli.return_value = True

        self.mock_process_web_cli_patcher = patch("manage_agenda.cli.process_web_cli")
        self.mock_process_web_cli = self.mock_process_web_cli_patcher.start()
        self.mock_process_web_cli.return_value = True

        self.mock_select_api_source_patcher = patch("manage_agenda.utils.select_api_source")
        self.mock_select_api_source = self.mock_select_api_source_patcher.start()
        self.mock_api_dst = MagicMock()
        self.mock_api_dst.getClient.return_value = True
        self.mock_select_api_source.return_value = self.mock_api_dst


    def tearDown(self):
        self.mock_get_add_sources_patcher.stop()
        self.mock_select_llm_patcher.stop()
        self.mock_process_email_cli_patcher.stop()
        self.mock_process_web_cli_patcher.stop()
        self.mock_select_api_source_patcher.stop()
        super().tearDown()


    @patch("manage_agenda.cli.authorize")
    def test_auth_command(self, mock_authorize):
        result = self.runner.invoke(self.cli.cli, ["auth"])
        self.assertEqual(result.exit_code, 0)
        mock_authorize.assert_called_once()

    @patch("manage_agenda.cli.select_api_source")
    @patch("manage_agenda.cli.list_events_folder")
    def test_gcalendar_command(self, mock_list_events_folder, mock_select_api_source):
        result = self.runner.invoke(self.cli.cli, ["gcalendar"])
        self.assertEqual(result.exit_code, 0)
        mock_select_api_source.assert_called_once()
        mock_list_events_folder.assert_called_once()

    @patch("manage_agenda.cli.list_emails_folder")
    def test_gmail_command(self, mock_list_emails_folder):
        result = self.runner.invoke(self.cli.cli, ["gmail"])
        self.assertEqual(result.exit_code, 0)
        mock_list_emails_folder.assert_called_once()

    def test_add_non_interactive(self):
        # All necessary mocks are set up in setUp
        result = self.runner.invoke(self.cli.cli, ["add", "-s", self.llm_name])
        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once() # Now using self.mock_process_email_cli

    def test_add_no_posts(self):
        # Mock api_src to return no posts
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "Label_0"}]
        mock_api_src.getPosts.return_value = []

        # Temporarily override the mock_module_rules for this test
        with patch.object(self.mock_module_rules, 'return_value') as mock_rules_instance_inner:
            mock_rules_instance_inner.selectRule.return_value = ["mocked_rule"]
            mock_rules_instance_inner.more.get.return_value = {"key": "value"}
            mock_rules_instance_inner.readConfigSrc.return_value = mock_api_src

            result = self.runner.invoke(self.cli.cli, ["add", "-s", self.llm_name])
            self.assertEqual(result.exit_code, 0)
            self.mock_process_email_cli.assert_called_once()


    def _mock_api(self, mock_process_email_cli):
        # This helper is probably not needed anymore with setUp
        pass

    def test_add_verbose_flag(self):
        # All necessary mocks are set up in setUp
        result = self.runner.invoke(self.cli.cli, ["-v", "add", "-s", self.llm_name])
        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once()


    def test_add_interactive_web(self):
        """Test add command in interactive mode selecting web source."""
        # Configure select_from_list for this specific test
        self.mock_select_from_list.return_value = (2, "Web (Enter URL)")

        result = self.runner.invoke(self.cli.cli, ["add", "-i"])

        self.assertEqual(result.exit_code, 0)
        self.mock_get_add_sources.assert_called_once()
        self.mock_process_web_cli.assert_called_once()

    def test_add_interactive_email(self):
        """Test add command in interactive mode selecting email source."""
        # Configure select_from_list for this specific test
        self.mock_select_from_list.return_value = (0, "gmail1")

        result = self.runner.invoke(self.cli.cli, ["add", "-i"])

        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once()
        # Verify source_name was passed
        call_args = self.mock_process_email_cli.call_args
        self.assertEqual(call_args[1].get("source_name"), "gmail1")

    @patch("manage_agenda.cli.authorize")
    def test_auth_client_not_connected(self, mock_authorize):
        """Test auth command when client fails to connect."""
        mock_api = MagicMock()
        mock_api.getClient.return_value = None
        mock_api.confName.return_value = "/path/to/config"
        mock_api.getServer.return_value = "server"
        mock_api.getNick.return_value = "nick"
        mock_authorize.return_value = mock_api

        result = self.runner.invoke(self.cli.cli, ["auth"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Enable the Gcalendar API", result.output)

    @patch("manage_agenda.cli.authorize")
    def test_auth_verbose(self, mock_authorize):
        """Test auth command with verbose flag."""
        mock_api = MagicMock()
        mock_api.getClient.return_value = MagicMock()
        mock_authorize.return_value = mock_api

        result = self.runner.invoke(self.cli.cli, ["-v", "auth"])

        self.assertEqual(result.exit_code, 0)

    @patch("manage_agenda.cli.evaluate_models")
    @patch("manage_agenda.cli.select_email_prompt", return_value="test prompt")
    def test_llm_evaluate_no_prompt(self, mock_select_prompt, mock_evaluate):
        """Test llm evaluate command without prompt."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate"])

        self.assertEqual(result.exit_code, 0)
        mock_select_prompt.assert_called_once()
        mock_evaluate.assert_called_once_with("test prompt")

    @patch("manage_agenda.cli.evaluate_models")
    def test_llm_evaluate_with_prompt(self, mock_evaluate):
        """Test llm evaluate command with prompt argument."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate", "test prompt"])

        self.assertEqual(result.exit_code, 0)
        mock_evaluate.assert_called_once_with("test prompt")

    @patch("manage_agenda.cli.evaluate_models")
    @patch("manage_agenda.cli.select_email_prompt", return_value=None)
    def test_llm_evaluate_no_prompt_returned(self, mock_select_prompt, mock_evaluate):
        """Test llm evaluate when select_email_prompt returns None."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate"])

        self.assertEqual(result.exit_code, 0)
        mock_select_prompt.assert_called_once()
        mock_evaluate.assert_not_called()

    @patch("manage_agenda.cli.copy_events_cli")
    def test_copy_command(self, mock_copy):
        """Test copy command."""
        result = self.runner.invoke(
            self.cli.cli, ["copy", "-s", "cal1", "-d", "cal2", "-t", "meeting"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_copy.assert_called_once()

    @patch("manage_agenda.cli.delete_events_cli")
    def test_delete_command(self, mock_delete):
        """Test delete command."""
        result = self.runner.invoke(self.cli.cli, ["delete"])

        self.assertEqual(result.exit_code, 0)
        mock_delete.assert_called_once()

    @patch("manage_agenda.cli.move_events_cli")
    def test_move_command(self, mock_move):
        """Test move command."""
        result = self.runner.invoke(self.cli.cli, ["move"])

        self.assertEqual(result.exit_code, 0)
        mock_move.assert_called_once()


if __name__ == "__main__":
    unittest.main()