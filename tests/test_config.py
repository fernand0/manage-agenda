import unittest
from unittest.mock import patch, MagicMock
import logging
import sys

sys.path.append(".")

from manage_agenda.config import Config


class TestConfig(unittest.TestCase):
    def test_validate_valid_config(self):
        """Test that validate returns True with valid configuration."""
        with patch.object(Config, 'DEFAULT_TIMEZONE', 'Europe/Berlin'), \
             patch.object(Config, 'LOG_LEVEL', 'INFO'):
            result = Config.validate()
            self.assertTrue(result)

    def test_validate_invalid_timezone(self):
        """Test that validate catches invalid timezone."""
        with patch.object(Config, 'DEFAULT_TIMEZONE', 'Invalid/Timezone'), \
             patch.object(Config, 'LOG_LEVEL', 'INFO'), \
             patch('logging.warning') as mock_warning:
            result = Config.validate()
            self.assertFalse(result)
            mock_warning.assert_called()

    def test_validate_invalid_log_level(self):
        """Test that validate catches invalid log level."""
        with patch.object(Config, 'DEFAULT_TIMEZONE', 'Europe/Berlin'), \
             patch.object(Config, 'LOG_LEVEL', 'INVALID'), \
             patch('logging.warning') as mock_warning:
            result = Config.validate()
            self.assertFalse(result)
            mock_warning.assert_called()

    def test_get_api_key_gemini(self):
        """Test getting Gemini API key."""
        test_key = "test_gemini_key"
        with patch.object(Config, 'GEMINI_API_KEY', test_key):
            key = Config.get_api_key('gemini')
            self.assertEqual(key, test_key)

    def test_get_api_key_mistral(self):
        """Test getting Mistral API key."""
        test_key = "test_mistral_key"
        with patch.object(Config, 'MISTRAL_API_KEY', test_key):
            key = Config.get_api_key('mistral')
            self.assertEqual(key, test_key)

    def test_get_api_key_not_configured(self):
        """Test getting API key for unconfigured service."""
        with patch.object(Config, 'GEMINI_API_KEY', None), \
             patch('logging.warning') as mock_warning:
            key = Config.get_api_key('gemini')
            self.assertIsNone(key)
            mock_warning.assert_called_with("No API key configured for gemini")

    def test_get_api_key_unknown_service(self):
        """Test getting API key for unknown service."""
        with patch('logging.warning') as mock_warning:
            key = Config.get_api_key('unknown_service')
            self.assertIsNone(key)
            mock_warning.assert_called()


if __name__ == "__main__":
    unittest.main()
