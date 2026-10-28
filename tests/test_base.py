import logging
import sys
import unittest
from unittest.mock import patch

sys.path.append(".")

from manage_agenda.base import setup_logging


class TestUtilsBase(unittest.TestCase):
    @patch("logging.basicConfig")
    def test_setup_logging_no_logdir(self, mock_basic_config):
        """
        Tests that setup_logging configures logging to the default /tmp directory.
        """
        with (
            patch("manage_agenda.base.LOGDIR", ""),
            patch("manage_agenda.base.config.LOG_FILE", "/tmp/manage_agenda.log"),
        ):
            setup_logging(verbose=True)

        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        self.assertEqual(kwargs["filename"], "/tmp/manage_agenda.log")
        self.assertEqual(kwargs["level"], logging.DEBUG)

    @patch("logging.basicConfig")
    def test_setup_logging_with_logdir(self, mock_basic_config):
        """
        Tests that setup_logging configures logging to a specified directory.
        """
        with patch("manage_agenda.base.LOGDIR", "/var/log"):
            setup_logging()

        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        self.assertEqual(kwargs["filename"], "/var/log/manage_agenda.log")
