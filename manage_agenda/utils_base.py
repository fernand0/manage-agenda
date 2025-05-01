import logging
import os
import sys

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



def setup_logging():
    """Configures logging to stdout."""
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )



def safe_get(data, keys, default=""):
    """Safely retrieves nested values from a dictionary."""
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default


def select_from_list(options, identifier="", selector="", default=""):
    """Selects an option form an iterable element, based on some identifier

    We can make an initial selection of elements that contain 'selector'
    We can select based on numbers or in substrings of the elements
    of the list.
    """

    if options and (
        isinstance(options[0], dict)
        or (hasattr(options[0], "__slots__"))
        or hasattr(options[0], "name")
    ):
        names = [
            safe_get(
                el,
                [
                    identifier,
                ],
            )
            if isinstance(el, dict)
            else getattr(el, identifier)
            for el in options
        ]
    else:
        names = options
    sel = -1
    options_sel = names.copy()
    while isinstance(sel, str) or (sel < 0):
        for i, elem in enumerate(options_sel):
            if selector in elem:
                print(f"{i}) {elem}")
        msg = "Selection "
        msg += f"({default}) " if default else ""
        sel = input(msg)
        if sel == "":
            if default:
                sel = names.index(default)
                # indices_coincidentes = list(i for i, elemento in enumerate(mi_lista) if busqueda in elemento)
        elif sel.isdigit() and int(sel) not in range(len(options_sel)):
            sel = -1
        elif not sel.isdigit():
            options_sel = [opt for opt in options_sel if sel in opt]
            print(f"Options: {options_sel}")
            if len(options_sel) == 1:
                sel = names.index(options_sel[0])
        else:
            # Now we select the original number
            sel = names.index(options_sel[int(sel)])

    logging.info(f"Sel: {sel}")

    return sel, names[int(sel)]
