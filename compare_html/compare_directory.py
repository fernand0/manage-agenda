import glob
import os
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def extract_domain_and_path_from_url(url):
    """
    Extracts the domain and path from a given URL, excluding filename and date patterns.
    Returns a string in the format "domain/path".
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path

    # If path is empty or just a slash, return domain
    if not path or path == "/":
        return domain

    # Remove filename
    path_directory = os.path.dirname(path)

    # Remove date-like patterns from the path
    # Handles formats like /YYYY/MM/DD, /YYYY-MM-DD, /YYYY/MM, etc.
    path_directory = re.sub(r"/\d{4}/\d{1,2}/\d{1,2}", "", path_directory)
    path_directory = re.sub(r"/\d{4}-\d{1,2}-\d{1,2}", "", path_directory)
    path_directory = re.sub(r"/\d{4}/\d{1,2}", "", path_directory)
    path_directory = re.sub(r"/\d{4}-\d{1,2}", "", path_directory)
    path_directory = re.sub(r"/\d{4}", "", path_directory)  # Year only

    # Clean up path and join with domain
    final_path = path_directory.rstrip("/")
    if not final_path:
        return domain
    else:
        return f"{domain}{final_path}"


def generate_filename_from_url(url):
    """
    Generates a Linux-filesystem-safe filename from a URL.
    """
    # Remove scheme
    if "://" in url:
        url_without_scheme = url.split("://", 1)[1]
    else:
        url_without_scheme = url

    # Replace invalid characters (anything not alphanumeric, dot, or hyphen) with underscore
    safe_filename = re.sub(r"[^a-zA-Z0-9.-]", "_", url_without_scheme)

    # Truncate to 255 characters
    return safe_filename[:255]


def process_directory(directory):
    """
    Compares two HTML files in a given directory, removes common fragments
    from the second file, cleans it, and saves the result in the same directory.
    """
    print(f"Procesando directorio: {directory}")

    # Find files to compare, excluding previous results and subdirectories.
    all_paths = glob.glob(os.path.join(directory, "*"))
    source_files = [f for f in all_paths if os.path.isfile(f) and not f.endswith("resultado.html")]
    source_files.sort()  # Sort alphabetically for consistent order

    if len(source_files) != 2:
        print(
            f"  -> Se esperaban 2 ficheros, pero se encontraron {len(source_files)}. Saltando directorio."
        )
        return

    file1_path, file2_path = source_files
    output_path = os.path.join(directory, "resultado.html")

    print(f"  -> Fichero 1: {os.path.basename(file1_path)}")
    print(f"  -> Fichero 2: {os.path.basename(file2_path)}")

    try:
        content1, content2 = None, None
        # Try to read with UTF-8, fall back to latin-1
        try:
            with open(file1_path, encoding="utf-8") as f:
                content1 = f.read()
            with open(file2_path, encoding="utf-8") as f:
                content2 = f.read()
        except UnicodeDecodeError:
            print("  -> Fallo con UTF-8, intentando con 'latin-1'.")
            with open(file1_path, encoding="latin-1") as f:
                content1 = f.read()
            with open(file2_path, encoding="latin-1") as f:
                content2 = f.read()

        soup1 = BeautifulSoup(content1, "html.parser")
        soup2 = BeautifulSoup(content2, "html.parser")

        # Extract the text of all tags from the first file
        fragments1 = {
            tag.get_text(strip=True) for tag in soup1.find_all(True) if tag.get_text(strip=True)
        }

        # --- Comparison and Cleaning Logic ---
        for tag in soup2.find_all(True):
            tag_text = tag.get_text(strip=True)
            if tag_text and tag_text in fragments1:
                tag.decompose()

        for script in soup2.find_all("script"):
            script.decompose()

        for meta in soup2.find_all("meta"):
            if meta.attrs is None or "charset" not in meta.attrs:
                meta.decompose()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup2.prettify()))

        print(f"  -> Proceso completado. Resultado guardado en: {output_path}")

    except FileNotFoundError as e:
        print(f"  -> Error: Fichero no encontrado - {e}")
    except Exception as e:
        print(f"  -> Ocurrió un error inesperado: {e}")


if __name__ == "__main__":
    base_path = os.path.dirname(os.path.abspath(__file__))
    target_dirs = [d for d in glob.glob(os.path.join(base_path, "ex*")) if os.path.isdir(d)]

    if not target_dirs:
        print("No se encontraron directorios con el patrón 'ex*'.")
    else:
        for directory in sorted(target_dirs):  # Sort dirs for consistent order
            process_directory(directory)
        print("\nProcesado de todos los directorios finalizado.")
