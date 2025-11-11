import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import tempfile
import shutil

sys.path.append(".")

from manage_agenda.utils_web import extract_domain_and_path_from_url, reduce_html, CACHE_DIR


class TestUtilsWeb(unittest.TestCase):
    def test_extract_domain_simple(self):
        """Test extracting domain from simple URL."""
        url = "https://example.com"
        result = extract_domain_and_path_from_url(url)
        self.assertEqual(result, "example.com")

    def test_extract_domain_with_path(self):
        """Test extracting domain and path."""
        url = "https://example.com/blog/article.html"
        result = extract_domain_and_path_from_url(url)
        self.assertEqual(result, "example.com/blog")

    def test_extract_domain_with_date_pattern(self):
        """Test removing date patterns from path."""
        test_cases = [
            ("https://example.com/2024/01/15/article.html", "example.com"),
            ("https://example.com/blog/2024/01/article.html", "example.com/blog"),
            ("https://example.com/2024-01-15/article.html", "example.com"),
            ("https://example.com/news/2024/article.html", "example.com/news"),
        ]
        for url, expected in test_cases:
            with self.subTest(url=url):
                result = extract_domain_and_path_from_url(url)
                self.assertEqual(result, expected)

    def test_extract_domain_root_path(self):
        """Test URL with root path."""
        url = "https://example.com/"
        result = extract_domain_and_path_from_url(url)
        self.assertEqual(result, "example.com")

    def test_extract_domain_with_subdomain(self):
        """Test URL with subdomain."""
        url = "https://blog.example.com/post/article.html"
        result = extract_domain_and_path_from_url(url)
        self.assertEqual(result, "blog.example.com/post")


class TestReduceHtml(unittest.TestCase):
    def setUp(self):
        """Create a temporary cache directory for tests."""
        self.temp_cache = tempfile.mkdtemp()
        self.original_cache = CACHE_DIR
        # Patch CACHE_DIR globally
        import manage_agenda.utils_web
        manage_agenda.utils_web.CACHE_DIR = self.temp_cache

    def tearDown(self):
        """Clean up temporary cache directory."""
        if os.path.exists(self.temp_cache):
            shutil.rmtree(self.temp_cache)
        # Restore original CACHE_DIR
        import manage_agenda.utils_web
        manage_agenda.utils_web.CACHE_DIR = self.original_cache

    def test_reduce_html_first_time(self):
        """Test reduce_html when URL is not cached."""
        url = "https://example.com/test"
        html_content = """
        <html>
            <head><script>alert('test');</script></head>
            <body><p>Hello World</p></body>
        </html>
        """
        
        result = reduce_html(url, html_content)
        
        # Should return cleaned text without scripts
        self.assertIn("Hello World", result)
        self.assertNotIn("alert", result)
        
        # Cache file should be created
        safe_filename = "example.com"  # URL without /test becomes just domain
        cache_path = os.path.join(self.temp_cache, safe_filename)
        self.assertTrue(os.path.exists(cache_path))

    def test_reduce_html_cached_version(self):
        """Test reduce_html when URL is already cached."""
        url = "https://example.com/test"
        old_html = """
        <html>
            <body><p>Old content</p></body>
        </html>
        """
        new_html = """
        <html>
            <body>
                <p>Old content</p>
                <p>New content</p>
            </body>
        </html>
        """
        
        # First call to cache the old version
        reduce_html(url, old_html)
        
        # Second call with new content
        result = reduce_html(url, new_html)
        
        # Should only show new content (old content removed)
        self.assertIn("New content", result)
        # Old content should be decomposed/removed
        self.assertNotIn("<p>Old content</p>", result)

    def test_reduce_html_removes_scripts_and_meta(self):
        """Test that reduce_html removes script and meta tags."""
        url = "https://example.com/clean"
        html_content = """
        <html>
            <head>
                <script>var x = 1;</script>
                <meta name="description" content="test">
            </head>
            <body><p>Content</p></body>
        </html>
        """
        
        result = reduce_html(url, html_content)
        
        self.assertNotIn("script", result.lower())
        self.assertNotIn("meta", result.lower())
        self.assertIn("Content", result)

    def test_reduce_html_creates_cache_dir(self):
        """Test that reduce_html creates cache directory if it doesn't exist."""
        # Remove cache dir
        if os.path.exists(self.temp_cache):
            shutil.rmtree(self.temp_cache)
        
        url = "https://example.com/test"
        html = "<html><body>Test</body></html>"
        
        reduce_html(url, html)
        
        # Cache dir should be created
        self.assertTrue(os.path.exists(self.temp_cache))

    @patch('builtins.print')
    def test_reduce_html_prints_cache_messages(self, mock_print):
        """Test that reduce_html prints appropriate messages."""
        url = "https://example.com/msg"
        html = "<html><body>Test</body></html>"
        
        # First call - not cached
        reduce_html(url, html)
        mock_print.assert_called_with("URL no encontrada en cache. Descargando y guardando...")
        
        # Second call - cached
        mock_print.reset_mock()
        reduce_html(url, html)
        mock_print.assert_called_with("URL encontrada en cache. Comparando...")

    def test_reduce_html_safe_filename_generation(self):
        """Test that special characters in URL are converted to safe filename."""
        url = "https://example.com/path/to:file?param=1&other=2"
        html = "<html><body>Test</body></html>"
        
        reduce_html(url, html)
        
        # Check that a file was created with safe characters
        files = os.listdir(self.temp_cache)
        self.assertEqual(len(files), 1)
        # Should only contain safe characters
        filename = files[0]
        self.assertRegex(filename, r'^[a-zA-Z0-9._-]+$')


if __name__ == "__main__":
    unittest.main()
