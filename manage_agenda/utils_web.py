
import os
import re
import urllib.request
from bs4 import BeautifulSoup

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "manage_agenda")

def reduce_html(url):
    """
    Reduces the HTML content of a URL by comparing it with a cached version.
    Returns the new or unique content of the page.
    """
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # Generate a safe filename from the URL
    safe_filename = re.sub(r'[^a-zA-Z0-9.-]', '_', url)
    cached_file_path = os.path.join(CACHE_DIR, safe_filename)

    # Download new content
    try:
        with urllib.request.urlopen(url) as response:
            # Try to decode with UTF-8, fall back to latin-1 on error
            try:
                new_html = response.read().decode('utf-8')
            except UnicodeDecodeError:
                new_html = response.read().decode('latin-1', errors='ignore')
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

    if os.path.exists(cached_file_path):
        print("URL encontrada en cache. Comparando...")
        with open(cached_file_path, 'r', encoding='utf-8') as f:
            old_html = f.read()

        soup1 = BeautifulSoup(old_html, 'html.parser')
        soup2 = BeautifulSoup(new_html, 'html.parser')

        # Store the text of all tags from the old version in a set for quick lookup
        fragments1 = {tag.get_text(strip=True) for tag in soup1.find_all(True) if tag.get_text(strip=True)}

        # Decompose tags in the new version if their text content is in the old version
        for tag in soup2.find_all(True):
            tag_text = tag.get_text(strip=True)
            if tag_text and tag_text in fragments1:
                tag.decompose()
        
        # Clean up scripts and meta tags
        for script in soup2.find_all('script'):
            script.decompose()
        for meta in soup2.find_all('meta'):
            meta.decompose()

        # Update cache with the new version
        with open(cached_file_path, 'w', encoding='utf-8') as f:
            f.write(new_html)

        return soup2.prettify()
    else:
        print("URL no encontrada en cache. Descargando y guardando...")
        # Save the new HTML to the cache
        with open(cached_file_path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        
        # For the first time, we can return the full text after basic cleaning
        soup = BeautifulSoup(new_html, 'html.parser')
        for script in soup.find_all('script'):
            script.decompose()
        for meta in soup.find_all('meta'):
            meta.decompose()
        return soup.get_text(separator='\n', strip=True)
