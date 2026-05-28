import logging
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


def extract_relevant_script_content(soup):
    """
    Extracts content from script tags that might contain event information,
    such as JSON-LD or data objects.
    """
    script_content = []
    for script in soup.find_all("script"):
        # 1. JSON-LD is a common standard for structured data (events, etc.)
        if script.get("type") == "application/ld+json":
            if script.string:
                script_content.append(f"Structured Data (JSON-LD):\n{script.string.strip()}")
        
        # 2. Look for large data objects or specific keywords in regular scripts
        elif not script.get("src") and script.string:
            content = script.string.strip()
            # Heuristic: If it looks like a large JSON object or contains event keywords,
            # it might be an initial state or data dump.
            # We look for "window.__" or "EVENT_DATA" or similar common patterns.
            keywords = ["event", "schedule", "calendar", "date", "venue", "location", "price"]
            if (len(content) > 100 and 
                any(k.lower() in content.lower() for k in keywords) and
                ("{" in content or "[" in content)):
                # We don't want to include huge minified libraries, so we check for some structure
                # and limit the size if it doesn't look like pure data
                if len(content) < 10000: # Arbitrary limit for sanity
                    script_content.append(f"Possible Data Object:\n{content}")

    return "\n\n".join(script_content)


def is_error_content(soup):
    """
    Checks if the BeautifulSoup object contains common error indicators.
    """
    # Check title
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text().lower()
        error_titles = [
            "404 not found", "403 forbidden", "500 internal server error",
            "502 bad gateway", "503 service unavailable", "access denied",
            "page not found", "error", "security check", "checking your browser"
        ]
        if any(err in title_text for err in error_titles):
            return True

    # Check common error heading patterns
    for heading in soup.find_all(["h1", "h2"]):
        h_text = heading.get_text().lower()
        error_indicators = [
            "404", "500", "502", "503", "not found", "access denied", 
            "forbidden", "error occurred", "security check"
        ]
        if any(err in h_text for err in error_indicators):
            # Double check if it's just a small page with this heading
            if len(soup.get_text()) < 1000:
                return True

    return False


def reduce_html(url, post, force_refresh=False):
    """
    Reduces the HTML content of a URL by comparing it with a cached version.
    Returns the new or unique content of the page.

    Args:
        url: The URL being processed
        post: The HTML content to process
        force_refresh: If True, bypass cache comparison and return full content
    """
    if not post or not post.strip():
        logging.warning(f"Empty content received for {url}")
        return None

    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # Generate a safe filename from the processed URL
    processed_url = extract_domain_and_path_from_url(url)
    safe_filename = re.sub(r"[^a-zA-Z0-9.-]", "_", processed_url)
    cached_file_path = os.path.join(CACHE_DIR, safe_filename)

    new_html = post
    logging.debug(f"Post: {post}")

    soup = BeautifulSoup(new_html, "html.parser")

    # Detect error pages
    if is_error_content(soup):
        logging.warning(f"Error page detected for {url}")
        return None
    
    # Extract relevant script content before they are decomposed
    extra_script_data = extract_relevant_script_content(soup)

    if force_refresh:
        logging.info("Force refresh enabled. Returning full content after cleaning...")
        # Save the new HTML to the cache
        with open(cached_file_path, "w", encoding="utf-8") as f:
            f.write(new_html)

        # Return the full content after basic cleaning
        for script in soup.find_all("script"):
            script.decompose()
        for meta in soup.find_all("meta"):
            meta.decompose()
        result = soup.get_text(separator="\n", strip=True)
    elif os.path.exists(cached_file_path):
        logging.info("URL found in cache. Comparing...")
        with open(cached_file_path, encoding="utf-8") as f:
            old_html = f.read()

        soup1 = BeautifulSoup(old_html, "html.parser")
        soup2 = soup # use the already parsed soup

        # Store the text of all tags from the old version in a set for quick lookup
        fragments1 = {
            tag.get_text(strip=True) for tag in soup1.find_all(True) if tag.get_text(strip=True)
        }

        # Decompose tags in the new version if their text content is in the old version
        # We are more selective to avoid removing important data (dates, times, locations)
        # that might appear in other pages (e.g. in footers or sidebar links)
        protected_keywords = [
            "Lugar", "Hora", "Fecha", "Cuándo", "Dónde", "Precio", "Entrada",
            "Place", "Time", "Date", "When", "Where", "Price", "Location", "Address",
            "Dirección", "Ubicación"
        ]
        
        for tag in soup2.find_all(True):
            if not tag.parent: # Already decomposed
                continue
                
            tag_text = tag.get_text(strip=True)
            if not tag_text or tag_text not in fragments1:
                continue

            # Check if tag contains protected keywords
            if any(k.lower() in tag_text.lower() for k in protected_keywords):
                continue

            # Check for date and time patterns
            if (re.search(r"\d{1,2}:\d{2}", tag_text) or # Time
                re.search(r"\d{1,2}\s+de\s+[a-z]+", tag_text, re.IGNORECASE) or # Spanish date
                re.search(r"\d{1,2}/\d{1,2}", tag_text)): # Numeric date
                continue

            # Only decompose if it's likely boilerplate (e.g. contains links or is very long)
            # or if it's not a short text block that could be venue/artist name
            is_link = (tag.name == 'a' or tag.find('a'))
            if is_link or len(tag_text) > 200:
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
        logging.info("URL not found in cache. Downloading and storing it...")
        # Save the new HTML to the cache
        with open(cached_file_path, "w", encoding="utf-8") as f:
            f.write(new_html)

        # For the first time, we can return the full text after basic cleaning
        for script in soup.find_all("script"):
            script.decompose()
        for meta in soup.find_all("meta"):
            meta.decompose()
        result = soup.get_text(separator="\n", strip=True)

    if extra_script_data:
        result = f"{result}\n\n--- Extra Data Found in Scripts ---\n{extra_script_data}"

    return result
