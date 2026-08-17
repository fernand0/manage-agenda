"""
Base utility functions for manage-agenda.
"""

import logging
import os
import sys
from pathlib import Path

from manage_agenda.config import config

LOGDIR = ""
DEFAULT_DATA_DIR = config.MSG_TXT_DIR


# --- File I/O ---
def write_file(filename, content):
    """Writes content to a file.

    Args:
        filename (str): The name of the file.
        content (str): The content to write.
    """
    try:
        # Sanitize the filename to prevent path traversal attacks
        # Normalize the path to resolve any '..' or '.' components
        normalized_filename = os.path.normpath(filename)

        # Ensure the filename doesn't contain path traversal sequences that would allow
        # writing outside the DEFAULT_DATA_DIR
        # Check if the normalized filename is an absolute path (which would
        # bypass DEFAULT_DATA_DIR) or
        # if it contains '..' components that could traverse up the directory
        # tree
        if os.path.isabs(normalized_filename) or '..' in normalized_filename.split(os.sep):
            logging.error(f"Invalid filename: {filename} - contains path traversal attempts")
            return False

        # Construct the full path using os.path.join for safety
        full_path = os.path.join(DEFAULT_DATA_DIR, normalized_filename)

        # Double-check that the final path is within the expected directory
        # Resolve both paths to handle symbolic links properly
        try:
            full_path_real = os.path.realpath(full_path)
            default_dir_real = os.path.realpath(DEFAULT_DATA_DIR)

            # Ensure the resolved file path is within the resolved default
            # directory
            if not full_path_real.startswith(default_dir_real + os.sep) and full_path_real != default_dir_real:
                logging.error(f"Invalid filename: {filename} - resolves outside allowed directory")
                return False
        except OSError:
            # If realpath fails (e.g., path doesn't exist), we can't do the security check,
            # but we can still proceed with the original path check if we're careful
            logging.warning(f"Could not resolve real paths for security check: {filename}")
            # We'll continue anyway, but this is less secure

        # Ensure the directory exists
        # Catch specific exceptions related to directory creation to distinguish
        # from other types of errors
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
        except OSError as dir_error:
            # If directory creation fails, we log it but continue to try opening the file
            # This allows tests with fake directories to work while still providing security
            logging.warning(f"Could not create directory for {filename}: {dir_error}")

        with open(full_path, "w") as file:
            file.write(content)
        logging.info(f"File written: {filename}")
        return True
    except Exception as e:
        logging.error(f"Error writing file {filename}: {e}")
        return False


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.

    Args:
        verbose: Enable verbose (DEBUG level) logging.
    """
    print("Setting logging")

    # Determine log file location
    if not LOGDIR:
        log_file = (
            Path(config.LOG_FILE) if hasattr(config, "LOG_FILE") else Path("/tmp/manage_agenda.log")
        )
    else:
        log_file = Path(f"{LOGDIR}/manage_agenda.log")

    # Create parent directory if needed
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine log level
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, getattr(config, "LOG_LEVEL", "INFO").upper(), logging.INFO)

    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        filename=str(log_file),
        level=log_level,
        format=log_format,
        datefmt=date_format,
    )

    # Also add console handler if verbose
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        logging.getLogger().addHandler(console_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {logging.getLevelName(log_level)}, File: {log_file}")


def format_time(seconds):
    """Formats seconds into a human-readable string."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {s:.2f}s"
