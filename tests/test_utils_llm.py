import unittest
from unittest.mock import patch, MagicMock

from manage_agenda.utils_llm import LLMClient
from manage_agenda.utils_llm import OllamaClient, GeminiClient, MistralClient


class TestLLMUtils(unittest.TestCase):
    def test_init(self):
        llm_client = LLMClient()
        self.assertIsInstance(llm_client, LLMClient)

    @patch("manage_agenda.utils_llm.genai.configure")
    def test_get_name(self, mock_configure):
        mock_configure.return_value = None
        ollama_client = OllamaClient()
        self.assertEqual(ollama_client.get_name(), "OllamaClient")

        gemini_client = GeminiClient()
        self.assertEqual(gemini_client.get_name(), "GeminiClient")

        mistral_client = MistralClient()
        self.assertEqual(mistral_client.get_name(), "MistralClient")



