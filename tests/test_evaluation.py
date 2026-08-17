import unittest
from unittest.mock import patch

from manage_agenda.evaluation import evaluate_models
from manage_agenda.llm import OllamaClient
from manage_agenda.sources import Args


class TestEvaluateModels(unittest.TestCase):
    @patch("builtins.print")
    @patch("time.time", side_effect=[0, 1, 2, 3])
    @patch("manage_agenda.evaluation.OllamaClient.__init__", return_value=None)
    @patch.object(OllamaClient, "list_models")
    def test_evaluate_models(self, mock_list_models, mock_init, mock_time, mock_print):
        """Test evaluate_models function."""
        mock_list_models.return_value = [{"model": "llama2"}, {"model": "mistral"}]
        args = Args(
            interactive=False,
            delete=None,
            source=None,
            verbose=False,
            destination=None,
            text=None,
        )

        with patch.object(OllamaClient, "generate_text", return_value="Test response"):
            evaluate_models(args, prompt="test prompt")

        mock_list_models.assert_called_once()
        self.assertEqual(mock_init.call_count, 2)
        self.assertGreater(mock_print.call_count, 0)

    @patch("builtins.print")
    @patch("manage_agenda.evaluation.OllamaClient.__init__", return_value=None)
    @patch.object(OllamaClient, "list_models")
    @patch("manage_agenda.evaluation.process_email_cli")
    @patch("manage_agenda.evaluation.process_web_cli")
    @patch("manage_agenda.evaluation.process_txt_cli")
    def test_evaluate_models_by_type(
        self,
        mock_process_txt,
        mock_process_web,
        mock_process_email,
        mock_list_models,
        mock_init,
        mock_print,
    ):
        """Test evaluate_models function with eval_type option."""
        mock_list_models.return_value = [{"model": "llama2"}]
        args = Args(
            interactive=False,
            delete=None,
            source=None,
            verbose=False,
            destination=None,
            text=None,
        )

        evaluate_models(args, eval_type="email")
        mock_process_email.assert_called_once()
        mock_process_web.assert_not_called()
        mock_process_txt.assert_not_called()

        mock_process_email.reset_mock()

        evaluate_models(args, eval_type="web")
        mock_process_email.assert_not_called()
        mock_process_web.assert_called_once()
        mock_process_txt.assert_not_called()

        mock_process_web.reset_mock()

        evaluate_models(args, eval_type="txt")
        mock_process_email.assert_not_called()
        mock_process_web.assert_not_called()
        mock_process_txt.assert_called_once()
