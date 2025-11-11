import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import tempfile

sys.path.append(".")

from manage_agenda.utils_llm import (
    LLMClient,
    OllamaClient,
    GeminiClient,
    MistralClient,
    evaluate_models,
    load_config,
)


class TestLoadConfig(unittest.TestCase):
    def test_load_config_file_exists(self):
        """Test loading a valid config file."""
        config_content = "[section1]\napi_key=test_key_123\n"
        
        with patch("os.path.exists", return_value=True):
            with patch("configparser.ConfigParser.read") as mock_read:
                config = load_config("/fake/path/config.ini")
                mock_read.assert_called_once_with("/fake/path/config.ini")

    def test_load_config_file_not_found(self):
        """Test loading a non-existent config file."""
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError) as context:
                load_config("/fake/path/config.ini")
            self.assertIn("Config file not found", str(context.exception))


class TestLLMClient(unittest.TestCase):
    def test_init_base_class(self):
        """Test LLMClient base class initialization."""
        llm_client = LLMClient()
        self.assertIsInstance(llm_client, LLMClient)
        self.assertIsNone(llm_client.model_name)

    def test_generate_text_not_implemented(self):
        """Test that generate_text raises NotImplementedError."""
        llm_client = LLMClient()
        with self.assertRaises(NotImplementedError):
            llm_client.generate_text("test prompt")

    def test_get_name_not_implemented(self):
        """Test that get_name raises NotImplementedError."""
        llm_client = LLMClient()
        with self.assertRaises(NotImplementedError):
            llm_client.get_name()


class TestOllamaClient(unittest.TestCase):
    @patch("manage_agenda.utils_llm.select_from_list")
    @patch("manage_agenda.utils_llm.OllamaClient.list_models")
    def test_ollama_init_with_model_name(self, mock_list_models, mock_select):
        """Test OllamaClient initialization with model name."""
        client = OllamaClient(model_name="llama2")
        self.assertEqual(client.model_name, "llama2")
        mock_list_models.assert_not_called()
        mock_select.assert_not_called()

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "llama2"))
    @patch("manage_agenda.utils_llm.OllamaClient.list_models")
    def test_ollama_init_without_model_name(self, mock_list_models, mock_select):
        """Test OllamaClient initialization without model name."""
        mock_list_models.return_value = [{"model": "llama2"}, {"model": "mistral"}]
        
        client = OllamaClient(model_name="")
        
        mock_list_models.assert_called_once()
        mock_select.assert_called_once()
        self.assertIsNotNone(client.model_name)

    @patch("manage_agenda.utils_llm.chat")
    def test_ollama_generate_text_success(self, mock_chat):
        """Test OllamaClient generate_text success."""
        mock_response = MagicMock()
        mock_response.message.content = "Generated response"
        mock_chat.return_value = mock_response
        
        client = OllamaClient(model_name="llama2")
        result = client.generate_text("test prompt")
        
        self.assertEqual(result, "Generated response")
        mock_chat.assert_called_once()

    @patch("manage_agenda.utils_llm.chat", side_effect=Exception("API Error"))
    def test_ollama_generate_text_error(self, mock_chat):
        """Test OllamaClient generate_text error handling."""
        client = OllamaClient(model_name="llama2")
        result = client.generate_text("test prompt")
        
        self.assertIsNone(result)

    @patch("manage_agenda.utils_llm.ollama.list")
    def test_ollama_list_models(self, mock_list):
        """Test OllamaClient list_models."""
        mock_list.return_value = {"models": [{"model": "llama2"}, {"model": "mistral"}]}
        
        models = OllamaClient.list_models()
        
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["model"], "llama2")


class TestGeminiClient(unittest.TestCase):
    @patch("manage_agenda.utils_llm.genai.GenerativeModel")
    @patch("manage_agenda.utils_llm.genai.configure")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_gemini_init_with_model_name(self, mock_exists, mock_load_config, mock_configure, mock_model):
        """Test GeminiClient initialization with model name."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        client = GeminiClient(model_name="gemini-pro")
        
        self.assertEqual(client.model_name, "gemini-pro")
        mock_configure.assert_called_once_with(api_key="fake_api_key")
        mock_model.assert_called_once_with("gemini-pro")

    @patch("manage_agenda.utils_llm.genai.GenerativeModel")
    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "models/gemini-pro"))
    @patch("manage_agenda.utils_llm.GeminiClient.list_models")
    @patch("manage_agenda.utils_llm.genai.configure")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_gemini_init_without_model_name(self, mock_exists, mock_load_config, mock_configure, 
                                           mock_list_models, mock_select, mock_model):
        """Test GeminiClient initialization without model name."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        mock_model_obj = MagicMock()
        mock_model_obj.name = "models/gemini-pro"
        mock_list_models.return_value = [mock_model_obj]
        
        client = GeminiClient(model_name="")
        
        self.assertEqual(client.model_name, "gemini-pro")

    @patch("manage_agenda.utils_llm.genai.GenerativeModel")
    @patch("manage_agenda.utils_llm.genai.configure")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_gemini_generate_text_success(self, mock_exists, mock_load_config, mock_configure, mock_model):
        """Test GeminiClient generate_text success."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini response"
        mock_client.generate_content.return_value = mock_response
        mock_model.return_value = mock_client
        
        client = GeminiClient(model_name="gemini-pro")
        result = client.generate_text("test prompt")
        
        self.assertEqual(result, "Gemini response")

    @patch("manage_agenda.utils_llm.genai.GenerativeModel")
    @patch("manage_agenda.utils_llm.genai.configure")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_gemini_generate_text_error(self, mock_exists, mock_load_config, mock_configure, mock_model):
        """Test GeminiClient generate_text error handling."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = Exception("API Error")
        mock_model.return_value = mock_client
        
        client = GeminiClient(model_name="gemini-pro")
        result = client.generate_text("test prompt")
        
        self.assertIsNone(result)

    @patch("manage_agenda.utils_llm.genai.list_models")
    def test_gemini_list_models(self, mock_list):
        """Test GeminiClient list_models."""
        mock_model1 = MagicMock()
        mock_model1.name = "gemini-pro"
        mock_model2 = MagicMock()
        mock_model2.name = "gemini-flash"
        mock_list.return_value = [mock_model1, mock_model2]
        
        models = GeminiClient.list_models()
        
        self.assertEqual(len(models), 2)


class TestMistralClient(unittest.TestCase):
    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "mistral-small"))
    @patch("manage_agenda.utils_llm.Mistral")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_mistral_init(self, mock_exists, mock_load_config, mock_mistral, mock_select):
        """Test MistralClient initialization."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        # Mock list_models
        mock_mistral_instance = MagicMock()
        mock_models = MagicMock()
        mock_models.data = [MagicMock(id="mistral-small")]
        mock_mistral_instance.models.list.return_value = mock_models
        mock_mistral.return_value = mock_mistral_instance
        
        client = MistralClient(model_name="mistral-small")
        
        mock_mistral.assert_called_once_with(api_key="fake_api_key")

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "mistral-small"))
    @patch("manage_agenda.utils_llm.Mistral")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_mistral_generate_text_success(self, mock_exists, mock_load_config, mock_mistral_class, mock_select):
        """Test MistralClient generate_text success."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        mock_mistral = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mistral response"
        mock_mistral.chat.complete.return_value = mock_response
        mock_mistral_class.return_value = mock_mistral
        
        # Mock list_models
        mock_models = MagicMock()
        mock_models.data = [MagicMock(id="mistral-small")]
        mock_mistral.models.list.return_value = mock_models
        
        client = MistralClient(model_name="mistral-small")
        result = client.generate_text("test prompt")
        
        self.assertEqual(result, "Mistral response")

    @patch("manage_agenda.utils_llm.select_from_list", return_value=(0, "mistral-small"))
    @patch("manage_agenda.utils_llm.Mistral")
    @patch("manage_agenda.utils_llm.load_config")
    @patch("os.path.exists", return_value=True)
    def test_mistral_generate_text_error(self, mock_exists, mock_load_config, mock_mistral_class, mock_select):
        """Test MistralClient generate_text error handling."""
        mock_config = MagicMock()
        mock_config.sections.return_value = ["section1"]
        mock_config.get.return_value = "fake_api_key"
        mock_load_config.return_value = mock_config
        
        mock_mistral = MagicMock()
        mock_mistral.chat.complete.side_effect = Exception("API Error")
        mock_mistral_class.return_value = mock_mistral
        
        # Mock list_models
        mock_models = MagicMock()
        mock_models.data = [MagicMock(id="mistral-small")]
        mock_mistral.models.list.return_value = mock_models
        
        client = MistralClient(model_name="mistral-small")
        result = client.generate_text("test prompt")
        
        self.assertIsNone(result)


class TestEvaluateModels(unittest.TestCase):
    @patch("builtins.print")
    @patch("time.time", side_effect=[0, 1, 2, 3])  # Mock time for duration calculation
    @patch("manage_agenda.utils_llm.OllamaClient.__init__", return_value=None)
    @patch.object(OllamaClient, 'list_models')
    def test_evaluate_models(self, mock_list_models, mock_init, mock_time, mock_print):
        """Test evaluate_models function."""
        mock_list_models.return_value = [
            {"model": "llama2"},
            {"model": "mistral"}
        ]
        
        # Mock generate_text method
        with patch.object(OllamaClient, 'generate_text', return_value="Test response"):
            evaluate_models("test prompt")
        
        # list_models should be called once
        mock_list_models.assert_called_once()
        # Should create 2 clients (one per model)
        self.assertEqual(mock_init.call_count, 2)
        # Should print results
        self.assertGreater(mock_print.call_count, 0)


if __name__ == "__main__":
    unittest.main()

