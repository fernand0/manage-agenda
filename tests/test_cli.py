import unittest
from collections import namedtuple
from unittest.mock import MagicMock, patch

from click.testing import CliRunner


class TestCliCommands(unittest.TestCase):

    # Class-level patchers
    mock_module_rules_patcher = patch("manage_agenda.utils.moduleRules")
    mock_select_from_list_patcher = patch("manage_agenda.utils.select_from_list")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Start class-level patchers
        cls.mock_module_rules_class = cls.mock_module_rules_patcher.start()
        cls.mock_select_from_list_class = cls.mock_select_from_list_patcher.start()

        # Configure class-level mocks
        cls.mock_rules_instance_class = MagicMock()
        cls.mock_module_rules_class.return_value = cls.mock_rules_instance_class
        cls.mock_module_rules_class.from_config.return_value = cls.mock_rules_instance_class
        cls.mock_rules_instance_class.checkRules.return_value = None
        cls.mock_rules_instance_class.selectRule.return_value = ["gmail1"]
        cls.mock_rules_instance_class.readConfigSrc.return_value = MagicMock()
        cls.mock_rules_instance_class.selectRuleInteractive.return_value = "gmail1"  # Default

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
        self.llm_name = "ollama"
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )
        self.runner = CliRunner()

        # Access class-level mocks via self
        self.mock_module_rules = self.mock_module_rules_class
        self.mock_select_from_list = self.mock_select_from_list_class
        self.mock_rules_instance = self.mock_rules_instance_class
        # Reset call history on the class-level mocks so each test starts fresh.
        # This prevents previous tests from affecting assert_called_once checks.
        try:
            self.mock_select_from_list.reset_mock()
        except Exception:
            pass
<<<<<<< HEAD
        self.mock_rules_instance = self.mock_rules_instance_class
=======
>>>>>>> 32c097816e18444da63d60771c872e62545cd7f5
        try:
            self.mock_rules_instance.selectRuleInteractive.reset_mock()
        except Exception:
            pass


        # Individual patches that apply per test method
        self.mock_get_add_sources_patcher = patch("manage_agenda.utils.get_add_sources")
        self.mock_get_add_sources = self.mock_get_add_sources_patcher.start()
        self.mock_get_add_sources.return_value = (["gmail1", "imap1"], ["web", ("http", "set", "(Enter URLs or leave empty)"), ("text", "set", "(enter filenames or leave empty)")])

        self.mock_select_llm_patcher = patch("manage_agenda.utils.select_llm")
        self.mock_select_llm = self.mock_select_llm_patcher.start()
        self.mock_llm = MagicMock()
        self.mock_select_llm.return_value = self.mock_llm

        self.mock_process_email_cli_patcher = patch("manage_agenda.utils.process_email_cli")

        self.mock_process_email_cli = self.mock_process_email_cli_patcher.start()
        self.mock_process_email_cli.return_value = True

        self.mock_process_web_cli_patcher = patch("manage_agenda.utils.process_web_cli")
        self.mock_process_web_cli = self.mock_process_web_cli_patcher.start()
        self.mock_process_web_cli.return_value = True

        self.mock_select_api_patcher = patch("manage_agenda.utils.select_api")
        self.mock_select_api = self.mock_select_api_patcher.start()
        self.mock_api_dst = MagicMock()
        self.mock_api_dst.getClient.return_value = True
        self.mock_select_api.return_value = self.mock_api_dst



    def tearDown(self):
        self.mock_get_add_sources_patcher.stop()
        self.mock_select_llm_patcher.stop()
        self.mock_process_email_cli_patcher.stop()
        self.mock_process_web_cli_patcher.stop()
        self.mock_select_api_patcher.stop()

        super().tearDown()


    @patch("manage_agenda.cli.authorize")
    def test_auth_command(self, mock_authorize):
        result = self.runner.invoke(self.cli.cli, ["auth"])
        self.assertEqual(result.exit_code, 0)
        mock_authorize.assert_called_once()

    @patch("manage_agenda.cli.moduleRules")
    @patch("manage_agenda.cli.list_events_folder")
    def test_gcalendar_command(self, mock_list_events_folder, mock_cli_module_rules):
        mock_cli_rules = MagicMock()
        mock_cli_module_rules.from_config.return_value = mock_cli_rules
        mock_cli_rules.selectRuleInteractive.return_value = self.mock_api_dst
        result = self.runner.invoke(self.cli.cli, ["gcalendar"])
        self.assertEqual(result.exit_code, 0)
        mock_cli_rules.selectRuleInteractive.assert_called_once()
        mock_list_events_folder.assert_called_once()

    @patch("manage_agenda.cli.list_emails_folder")
    def test_gmail_command(self, mock_list_emails_folder):
        result = self.runner.invoke(self.cli.cli, ["gmail"])
        self.assertEqual(result.exit_code, 0)
        mock_list_emails_folder.assert_called_once()

    def test_add_non_interactive(self):
        # All necessary mocks are set up in setUp
        result = self.runner.invoke(self.cli.cli, ["add", "-s", "gmail"])
        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once() # Now using self.mock_process_email_cli

    def test_add_no_posts(self):
        result = self.runner.invoke(self.cli.cli, ["add", "-s", "gmail"])
        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once()


    def _mock_api(self, mock_process_email_cli):
        # This helper is probably not needed anymore with setUp
        pass

    def test_add_verbose_flag(self):
        # All necessary mocks are set up in setUp
        result = self.runner.invoke(self.cli.cli, ["-v", "add", "-s", "gmail"])
        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once()


    def test_add_interactive_web(self):
        """Test add command in interactive mode with web source."""
        self.mock_rules_instance.selectRuleInteractive.return_value = "web"

        result = self.runner.invoke(self.cli.cli, ["add", "-i", "-s", "web"])

        self.assertEqual(result.exit_code, 0)
        self.mock_rules_instance.selectRuleInteractive.assert_called_once()
        self.mock_process_web_cli.assert_called_once()

    def test_add_interactive_email(self):
        """Test add command in interactive mode selecting email source."""
        self.mock_rules_instance.selectRuleInteractive.return_value = "gmail1"

        result = self.runner.invoke(self.cli.cli, ["add", "-i"])

        self.assertEqual(result.exit_code, 0)
<<<<<<< HEAD
        self.mock_rules_instance.selectRuleInteractive.assert_called_once()
=======
        self.mock_rules_instance.selectRuleInteractive.assert_called()
>>>>>>> 32c097816e18444da63d60771c872e62545cd7f5
        self.mock_process_email_cli.assert_called_once()

    def test_add_with_destination_and_output(self):
        """Test add command with both --destination and --output options."""
        result = self.runner.invoke(
            self.cli.cli, ["add", "-s", "gmail", "-d", "specific_cal", "-o", "file"]
        )

        self.assertEqual(result.exit_code, 0)
        self.mock_process_email_cli.assert_called_once()
        # Verify both destination and output were correctly passed to Args
        call_args = self.mock_process_email_cli.call_args
        args = call_args[0][0]
        self.assertEqual(args.destination, "specific_cal")
        self.assertEqual(args.output, "file")

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
    def test_llm_evaluate_no_prompt(self, mock_evaluate):
        """Test llm evaluate command without prompt."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate"])

        self.assertEqual(result.exit_code, 0)
        mock_evaluate.assert_called_once()
        args, kwargs = mock_evaluate.call_args
        self.assertIsNone(kwargs.get("prompt"))
        self.assertEqual(kwargs.get("eval_type"), "txt")

    @patch("manage_agenda.cli.evaluate_models")
    def test_llm_evaluate_with_prompt(self, mock_evaluate):
        """Test llm evaluate command with prompt argument."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate", "test prompt"])

        self.assertEqual(result.exit_code, 0)
        mock_evaluate.assert_called_once()
        args, kwargs = mock_evaluate.call_args
        self.assertEqual(kwargs.get("prompt"), "test prompt")
        self.assertIsNone(kwargs.get("eval_type"))

    @patch("manage_agenda.cli.evaluate_models")
    def test_llm_evaluate_with_type(self, mock_evaluate):
        """Test llm evaluate command with type option."""
        result = self.runner.invoke(self.cli.cli, ["llm", "evaluate", "--type", "email"])

        self.assertEqual(result.exit_code, 0)
        mock_evaluate.assert_called_once()
        args, kwargs = mock_evaluate.call_args
        self.assertIsNone(kwargs.get("prompt"))
        self.assertEqual(kwargs.get("eval_type"), "email")

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
