import os
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "manage_agenda")


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
    if ((path_directory == path) or (path_directory == path[:-1])):
        new_path = os.path.split(path_directory)[0]
        if new_path:
            path_directory = new_path


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


def reduce_html(url, post):
    """
    Reduces the HTML content of a URL by comparing it with a cached version.
    Returns the new or unique content of the page.
    """
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # Generate a safe filename from the processed URL
    processed_url = extract_domain_and_path_from_url(url)
    safe_filename = re.sub(r"[^a-zA-Z0-9.-]", "_", processed_url)
    cached_file_path = os.path.join(CACHE_DIR, safe_filename)

    new_html = post
    logging.debug(f"Post: {post}")

    if os.path.exists(cached_file_path):
        logging.info("URL encontrada en cache. Comparando...")
        with open(cached_file_path, encoding="utf-8") as f:
            old_html = f.read()

        soup1 = BeautifulSoup(old_html, "html.parser")
        soup2 = BeautifulSoup(new_html, "html.parser")

        # Store the text of all tags from the old version in a set for quick lookup
        fragments1 = {
            tag.get_text(strip=True) for tag in soup1.find_all(True) if tag.get_text(strip=True)
        }

        # Decompose tags in the new version if their text content is in the old version
        for tag in soup2.find_all(True):
            tag_text = tag.get_text(strip=True)
            if (
                ("Lugar" not in tag_text)
                and ("Hora" not in tag_text)
                # Particular case for cultura.unizar.es ??
                and tag_text
                and tag_text in fragments1
            ):
                tag.decompose()

        # Clean up scripts and meta tags
        for script in soup2.find_all("script"):
            script.decompose()
        for meta in soup2.find_all("meta"):
            meta.decompose()

        # result = soup2.prettify()
        result = soup2.get_text(separator="\n", strip=True)
        # Update cache with the new version
        with open(cached_file_path, "w", encoding="utf-8") as f:
            f.write(new_html)

    else:
        print("URL not found in cache. Downloading and storing it...")
        # Save the new HTML to the cache
        with open(cached_file_path, "w", encoding="utf-8") as f:
            f.write(new_html)

        # For the first time, we can return the full text after basic cleaning
        soup = BeautifulSoup(new_html, "html.parser")
        for script in soup.find_all("script"):
            script.decompose()
        for meta in soup.find_all("meta"):
            meta.decompose()
        result = soup.get_text(separator="\n", strip=True)

    return result
