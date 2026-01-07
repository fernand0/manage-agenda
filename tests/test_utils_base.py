import logging
import sys
import unittest
from unittest.mock import mock_open, patch

sys.path.append(".")

from manage_agenda.utils_base import setup_logging, write_file


class TestUtilsBase(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open)
    @patch("logging.info")
    def test_write_file_success(self, mock_logging_info, mock_open_file):
        """
        Tests that write_file successfully writes content to a file.
        """
        filename = "test.txt"
        content = "This is a test."

        # We need to mock DEFAULT_DATA_DIR or the function will fail
        with patch("manage_agenda.utils_base.DEFAULT_DATA_DIR", "/fake/dir/"):
            write_file(filename, content)

        mock_open_file.assert_called_once_with("/fake/dir/test.txt", "w")
        mock_open_file().write.assert_called_once_with(content)
        mock_logging_info.assert_called_once_with(f"File written: {filename}")

    @patch("builtins.open", side_effect=OSError("Disk full"))
    @patch("logging.error")
    def test_write_file_failure(self, mock_logging_error, mock_open_file):
        """
        Tests that write_file logs an error when it fails to write a file.
        """
        filename = "test.txt"
        content = "This is a test."

        with patch("manage_agenda.utils_base.DEFAULT_DATA_DIR", "/fake/dir/"):
            write_file(filename, content)

        mock_open_file.assert_called_once_with("/fake/dir/test.txt", "w")
        self.assertIn("Error writing file", mock_logging_error.call_args[0][0])

    @patch("logging.basicConfig")
    def test_setup_logging_no_logdir(self, mock_basic_config):
        """
        Tests that setup_logging configures logging to the default /tmp directory.
        """
        with (
            patch("manage_agenda.utils_base.LOGDIR", ""),
            patch("manage_agenda.utils_base.config.LOG_FILE", "/tmp/manage_agenda.log"),
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
        with patch("manage_agenda.utils_base.LOGDIR", "/var/log"):
            setup_logging()

        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        self.assertEqual(kwargs["filename"], "/var/log/manage_agenda.log")
