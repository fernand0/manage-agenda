import json
import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import datetime


class TestCli(unittest.TestCase):
    def setUp(self):
        from manage_agenda import cli

        self.cli = cli
        self.runner = CliRunner()

    def test_add_non_interactive(self):
        with patch("manage_agenda.cli.select_llm") as mock_select_llm, patch(
            "manage_agenda.cli.process_email_cli"
        ) as mock_process_email_cli:
            # Mock the LLM client
            mock_llm_client = MagicMock()
            mock_llm_client.generate_text.return_value = '{"start": {"dateTime": "2024-12-12T10:00:00"}, "end": {"dateTime": "2024-12-12T11:00:00"}}'  # Example JSON response
            mock_select_llm.return_value = mock_llm_client

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

            result = self.runner.invoke(
                self.cli.cli, ["add", "-s", "gemini", "-d", "False"]
            )
            self.assertEqual(result.exit_code, 0)
            mock_select_llm.assert_called_once()
            mock_process_email_cli.assert_called_once()