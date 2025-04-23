import json
import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import datetime


class TestCli(unittest.TestCase):
    def setUp(self):
        from manage_agenda import cli

        self.cli = cli
        self.llm_name = "gemini"
        self.runner = CliRunner()

    def test_add_non_interactive(self):
        with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
            # Mock the LLM client
            mock_llm_client = MagicMock()
            mock_llm_client.generate_text.return_value = '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'  # Example JSON response
            mock_select_llm.return_value = mock_llm_client            
            self._mock_api(mock_process_email_cli)

            result = self.runner.invoke(
                self.cli.cli, ["add", "-s", self.llm_name, "-d", "False"]
            )
            self.assertEqual(result.exit_code, 0)
            mock_select_llm.assert_called_once_with(self.llm_name)
            mock_process_email_cli.assert_called_once()
    
    def test_add_non_interactive_d_true(self):
        with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli, patch(
            "manage_agenda.cli.datetime"
        ) as mock_datetime:
            # Mock the LLM client
            mock_llm_client = MagicMock()
            mock_llm_client.generate_text.return_value = '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'  # Example JSON response
            mock_select_llm.return_value = mock_llm_client            
            self._mock_api(mock_process_email_cli)

            today = datetime.date(2023,12,7)
            mock_datetime.date.today.return_value = today

            result = self.runner.invoke(
                self.cli.cli, ["add", "-s", self.llm_name, "-d", "True"]
            )
            self.assertEqual(result.exit_code, 0)
            mock_select_llm.assert_called_once_with(self.llm_name)
            mock_process_email_cli.assert_called_once()

    def test_add_invalid_json(self):
        with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
            # Mock the LLM client to return invalid JSON
            mock_llm_client = MagicMock()
            mock_llm_client.generate_text.return_value = 'this is not json'
            mock_select_llm.return_value = mock_llm_client            
            self._mock_api(mock_process_email_cli)

            result = self.runner.invoke(
                self.cli.cli, ["add", "-s", self.llm_name, "-d", "False"]
            )
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid JSON", result.output)
            mock_select_llm.assert_called_once_with(self.llm_name)
            
            mock_process_email_cli.assert_called_once()


    def _mock_api(self, mock_process_email_cli):
        # Mock api_src and api_dst
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id":"Label_0"}]
        mock_api_src.getPosts.return_value = ["post_id"]
        mock_api_src.getPostId.return_value = "post_id"
        mock_api_src.getPostDate.return_value = 1701937200000 #12/07/2023
        mock_api_src.getPostTitle.return_value = "Test title"
        mock_api_src.getPostBody.return_value = "Test Body"
        mock_api_src.getMessage.return_value = "message"
        mock_process_email_cli.side_effect = lambda args, model: None

    def test_select_llm_called(self):
        with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
            mock_llm_client = MagicMock()
            mock_llm_client.generate_text.return_value = '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'
            mock_select_llm.return_value = mock_llm_client
            mock_process_email_cli.side_effect = lambda args, model: None
            self._mock_api(mock_process_email_cli)
            self.runner.invoke(self.cli.cli, ["add", "-s", self.llm_name, "-d", "False"])
            mock_select_llm.assert_called_once_with(self.llm_name)
            mock_process_email_cli.assert_called_once()