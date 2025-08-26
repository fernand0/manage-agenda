import click
import logging
import os
import sys

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


def setup_logging(verbose=False):
    """Configures logging to stdout or a file."""
    print(f"Setting logging")
    if not LOGDIR:
        logFile = f"/tmp/manage_agenda.log"
    else:
        logFile = f"{LOGDIR}/manage_agenda.log"

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        filename = logFile,
        # stream=sys.stdout,
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
    )


def format_time(seconds):
    """Formats seconds into a human-readable string."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {s:.2f}s"

# def select_from_list(options, identifier="", selector="", default=""):
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