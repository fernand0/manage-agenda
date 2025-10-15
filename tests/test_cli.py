import json
import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import datetime

from collections import namedtuple


class TestCliCommands(unittest.TestCase):
    def setUp(self):
        from manage_agenda import cli
        self.cli = cli
        self.runner = CliRunner()

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

    @patch("manage_agenda.cli.select_api_source")
    @patch("manage_agenda.cli.list_emails_folder")
    def test_gmail_command(self, mock_list_emails_folder, mock_select_api_source):
        result = self.runner.invoke(self.cli.cli, ["gmail"])
        self.assertEqual(result.exit_code, 0)
        mock_select_api_source.assert_called_once()
        mock_list_emails_folder.assert_called_once()

    def setUp(self):
        from manage_agenda import cli

        self.cli = cli
        self.llm_name = "gemini"
        self.Args = namedtuple("args", ["interactive", "delete", "source", "verbose", "destination", "text"])
        self.runner = CliRunner()

    def test_add_non_interactive(self):
        with patch("manage_agenda.utils.GeminiClient") as mock_gemini_client, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
            # Mock the LLM client
            mock_llm_client = MagicMock()

            def generate_text_side_effect(prompt):
                return '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'

            mock_llm_client.generate_text.side_effect = generate_text_side_effect
            mock_gemini_client.return_value = mock_llm_client
            self._mock_api(mock_process_email_cli)

            result = self.runner.invoke(
                self.cli.cli, ["add", "-s", self.llm_name]
            )
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
        with patch("manage_agenda.utils.GeminiClient") as mock_gemini_client, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
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

            mock_process_email_cli.side_effect = lambda args, model: None

            with patch(
                "manage_agenda.utils.moduleRules.moduleRules"
            ) as mock_module_rules:
                mock_rules = MagicMock()
                mock_rules.selectRule.return_value = ["mocked_rule"]
                mock_rules.more.get.return_value = {"key": "value"}
                mock_rules.readConfigSrc.return_value = mock_api_src
                mock_module_rules.return_value = mock_rules

                result = self.runner.invoke(
                    self.cli.cli, ["add", "-s", self.llm_name]
                )
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
        mock_process_email_cli.side_effect = lambda args, model: None

    # def test_add_llm_returns_none(self):
    #     with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
    #         "manage_agenda.cli.process_email_cli"
    #     ) as mock_process_email_cli:
    #         # Mock the LLM client
    #         mock_llm_client = MagicMock()
    #         mock_llm_client.generate_text.return_value = None
    #         mock_select_llm.return_value = mock_llm_client
    #         self._mock_api(mock_process_email_cli)

    #         result = self.runner.invoke(
    #             self.cli.cli, ["add", "-s", self.llm_name, "-d", "False"]
    #         )
    #         self.assertEqual(result.exit_code, 0)
    #         self.assertIn("Failed to get response from LLM", result.output)
    #         expected_args = self.Args(interactive=False, delete=True, source=self.llm_name)
    #         mock_select_llm.assert_called_once_with(expected_args)
    #         mock_process_email_cli.assert_called_once()
