import os
import re
import sys
import urllib.request
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def download_url(url):
    """
    Downloads the HTML content of a URL and returns it as a string.
    """
    try:
        with urllib.request.urlopen(url) as response:
            # Try to decode with UTF-8, fall back to latin-1 on error
            try:
                return response.read().decode("utf-8")
            except UnicodeDecodeError:
                return response.read().decode("latin-1", errors="ignore")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python compare.py <URL>")
        sys.exit(1)

    input_url = sys.argv[1]

    # Create cache directory if it doesn't exist
    CACHE_DIR = "cache"
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    processed_url_path = extract_domain_and_path_from_url(input_url)
    generated_filename = generate_filename_from_url(processed_url_path)
    cached_file_path = os.path.join(CACHE_DIR, generated_filename)

    if os.path.exists(cached_file_path):
        print("URL encontrada en cache. Comparando...")

        new_html = download_url(input_url)
        if not new_html:
            sys.exit(1)

        with open(cached_file_path, encoding="utf-8") as f:
            old_html = f.read()

        soup1 = BeautifulSoup(old_html, "html.parser")
        soup2 = BeautifulSoup(new_html, "html.parser")

        fragments1 = {
            tag.get_text(strip=True) for tag in soup1.find_all(True) if tag.get_text(strip=True)
        }

        for tag in soup2.find_all(True):
            tag_text = tag.get_text(strip=True)
            if tag_text and tag_text in fragments1:
                tag.decompose()

        # Clean up scripts and meta tags as before
        for script in soup2.find_all("script"):
            script.decompose()
        for meta in soup2.find_all("meta"):
            meta.decompose()

        print("\n--- Contenido Nuevo ---\n")
        print(soup2.prettify())

    else:
        print("URL no encontrada en cache. Descargando y guardando...")
        html_content = download_url(input_url)
        if html_content:
            with open(cached_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Guardado en cache como: {cached_file_path}")
