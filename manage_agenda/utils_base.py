"""
Base utility functions for manage-agenda.
"""
import click
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from manage_agenda.config import config

LOGDIR = ""
DEFAULT_DATA_DIR = os.path.expanduser("~/Documents/data/msgs/")


# --- File I/O ---
def write_file(filename, content):
    """Writes content to a file.

    Args:
        filename (str): The name of the file.
        content (str): The content to write.
    """
    try:
        with open(f"{DEFAULT_DATA_DIR}{filename}", "w") as file:
            file.write(content)
        logging.info(f"File written: {filename}")
    except Exception as e:
        logging.error(f"Error writing file {filename}: {e}")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.
    
    Args:
        verbose: Enable verbose (DEBUG level) logging.
    """
    print(f"Setting logging")
    
    # Determine log file location
    if not LOGDIR:
        log_file = Path(config.LOG_FILE) if hasattr(config, 'LOG_FILE') else Path("/tmp/manage_agenda.log")
    else:
        log_file = Path(f"{LOGDIR}/manage_agenda.log")
    
    # Create parent directory if needed
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine log level
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, getattr(config, 'LOG_LEVEL', 'INFO').upper(), logging.INFO)
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
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
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        logging.getLogger().addHandler(console_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {logging.getLevelName(log_level)}, File: {log_file}")


def format_time(seconds):
    """Formats seconds into a human-readable string."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {s:.2f}s"
#     """selects an option form an iterable element, based on some identifier
#
#     we can make an initial selection of elements that contain 'selector'
#     we can select based on numbers or in substrings of the elements
#     of the list.
#     """
#
#     if options and (
#         isinstance(options[0], dict)
#         or (hasattr(options[0], "__slots__"))
#         or hasattr(options[0], "name")
#     ):
#         names = [
#             safe_get(
#                 el,
#                 [
#                     identifier,
#                 ],
#             )
#             if isinstance(el, dict)
#             else getattr(el, identifier)
#             for el in options
#         ]
#     else:
#         names = options
#     sel = -1
#     names_sel = [opt for opt in names if selector in opt]
#     options_sel = names_sel.copy()
#     while options_sel:
#         text_sel = ""
#         for i, elem in enumerate(options_sel):
#             text_sel = f"{text_sel}\n{i}) {elem}"
#         resPopen = os.popen('stty size', 'r').read()
#         rows, columns = resPopen.split()
#         if text_sel.count('\n') > int(rows) -2:
#             click.echo_via_pager(text_sel)
#         else:
#             click.echo(text_sel)
#         msg = "Selection"
#         # msg += f"({default}) " if default else ""
#         sel = click.prompt(msg, default=default)
#         if sel == "" and default:
#                 sel = names.index(default)
#                 options_sel = []
#         elif not sel.isdigit():
#             options_sel = [opt for opt in options_sel if sel in opt]
#             if len(options_sel) == 1:
#                 sel = names.index(options_sel[0])
#                 options_sel = []
#             elif len(options_sel) == 0:
#                 options_sel = names_sel.copy()
#         else:
#             # Now we select the original number
#             if int(sel) < len(options_sel):
#                 sel = names.index(options_sel[int(sel)])
#                 options_sel = []
#             else:
#                 options_sel = names_sel.copy()
#
#     logging.info(f"Sel: {sel} - {names[int(sel)]}")
#
#     return sel, names[int(sel)]
