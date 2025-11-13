import unittest
from collections import namedtuple
from unittest.mock import MagicMock, patch

from click.testing import CliRunner


class TestCliCommands(unittest.TestCase):


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

    def setUp(self):
        from manage_agenda import cli

        self.cli = cli
        self.llm_name = "gemini"
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )
        self.runner = CliRunner()

    def test_add_non_interactive(self):
        with (
            patch("manage_agenda.utils.GeminiClient") as mock_gemini_client,
            patch("manage_agenda.cli.process_email_cli") as mock_process_email_cli,
        ):
            # Mock the LLM client
            mock_llm_client = MagicMock()

            def generate_text_side_effect(prompt):
                return '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'

            mock_llm_client.generate_text.side_effect = generate_text_side_effect
            mock_gemini_client.return_value = mock_llm_client
            self._mock_api(mock_process_email_cli)

            result = self.runner.invoke(self.cli.cli, ["add", "-s", self.llm_name])
            self.assertEqual(result.exit_code, 0)
            mock_process_email_cli.assert_called_once()

    # def test_add_select_llm_returns_none(self):
    #     with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
    #         "manage_agenda.cli.process_email_cli"
    #     ) as mock_process_email_cli:
    #         # Mock select_llm to return None
    #         mock_select_llm.return_value = None
    #
    #         mock_process_email_cli.side_effect = lambda args, model: None

    #         result = self.runner.invoke(
    #             self.cli.cli, ["add", "-s", self.llm_name, "-d", "False"]
    #         )
    #         self.assertEqual(result.exit_code, 1)
    #         self.assertIn("Invalid LLM", result.output)
    #         expected_args = self.Args(interactive=False, delete=True, source=self.llm_name)
    #         mock_select_llm.assert_called_once_with(expected_args)
    #         mock_process_email_cli.assert_not_called()

    def test_add_no_posts(self):
        with (
            patch("manage_agenda.utils.GeminiClient") as mock_gemini_client,
            patch("manage_agenda.cli.process_email_cli") as mock_process_email_cli,
        ):
            # Mock the LLM client
            mock_llm_client = MagicMock()

            def generate_text_side_effect(prompt):
                return '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'

            mock_llm_client.generate_text.side_effect = generate_text_side_effect
            mock_gemini_client.return_value = mock_llm_client

            # Mock api_src to return no posts
            mock_api_src = MagicMock()
            mock_api_src.service = "gmail"
            mock_api_src.getLabels.return_value = [{"id": "Label_0"}]
            mock_api_src.getPosts.return_value = []

            mock_process_email_cli.side_effect = lambda args, model: True

            with patch("manage_agenda.utils.moduleRules.moduleRules") as mock_module_rules:
                mock_rules = MagicMock()
                mock_rules.selectRule.return_value = ["mocked_rule"]
                mock_rules.more.get.return_value = {"key": "value"}
                mock_rules.readConfigSrc.return_value = mock_api_src
                mock_module_rules.return_value = mock_rules

                result = self.runner.invoke(self.cli.cli, ["add", "-s", self.llm_name])
                self.assertEqual(result.exit_code, 0)
                mock_process_email_cli.assert_called_once()

    def _mock_api(self, mock_process_email_cli):
        # Mock api_src and api_dst
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "Label_0"}]
        mock_api_src.getPosts.return_value = ["post_id"]
        mock_api_src.getPostId.return_value = "post_id"
        mock_api_src.getPostDate.return_value = 1701937200000  # 12/07/2023
        mock_api_src.getPostTitle.return_value = "Test title"
        mock_api_src.getPostBody.return_value = "Test Body"
        mock_api_src.getMessage.return_value = "message"
        mock_process_email_cli.side_effect = lambda args, model: True

    @patch("manage_agenda.cli.select_llm")
    @patch("manage_agenda.cli.process_email_cli")
    def test_add_verbose_flag(self, mock_process_email, mock_select_llm):
        """Test add command with verbose flag."""
        mock_llm = MagicMock()
        mock_select_llm.return_value = mock_llm
        mock_process_email.return_value = True

        result = self.runner.invoke(self.cli.cli, ["-v", "add", "-s", "gemini"])

        self.assertEqual(result.exit_code, 0)

    @patch("manage_agenda.cli.get_add_sources", return_value=["gmail", "web"])
    @patch("manage_agenda.cli.select_from_list", return_value=(1, "web"))
    @patch("manage_agenda.cli.select_llm")
    @patch("manage_agenda.cli.process_web_cli")
    def test_add_interactive_web(
        self, mock_process_web, mock_select_llm, mock_select_list, mock_get_sources
    ):
        """Test add command in interactive mode selecting web source."""
        mock_llm = MagicMock()
        mock_select_llm.return_value = mock_llm
        mock_process_web.return_value = True

        result = self.runner.invoke(self.cli.cli, ["add", "-i"])

        self.assertEqual(result.exit_code, 0)
        mock_get_sources.assert_called_once()
        mock_process_web.assert_called_once()

    @patch("manage_agenda.cli.get_add_sources", return_value=["gmail1", "imap1"])
    @patch("manage_agenda.cli.select_from_list", return_value=(0, "gmail1"))
    @patch("manage_agenda.cli.select_llm")
    @patch("manage_agenda.cli.process_email_cli")
    def test_add_interactive_email(
        self, mock_process_email, mock_select_llm, mock_select_list, mock_get_sources
    ):
        """Test add command in interactive mode selecting email source."""
        mock_llm = MagicMock()
        mock_select_llm.return_value = mock_llm
        mock_process_email.return_value = True

        result = self.runner.invoke(self.cli.cli, ["add", "-i"])

        self.assertEqual(result.exit_code, 0)
        mock_process_email.assert_called_once()
        # Verify source_name was passed
        call_args = mock_process_email.call_args
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
