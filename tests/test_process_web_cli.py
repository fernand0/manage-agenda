import unittest
from unittest.mock import MagicMock, patch, call
from collections import namedtuple

# Import the functions to be tested.
# Note: We might need to import them inside the test method if they are not
# exposed in __init__.py or if we want to patch them during import (though
# patch usually handles that).
from manage_agenda.utils import process_web_cli, _get_pages_from_urls, Args

class TestProcessWebCli(unittest.TestCase):
    def setUp(self):
        self.args = Args(
            interactive=False,
            delete=False,
            source=None,
            verbose=False,
            destination=None,
            text=None
        )
        self.model = MagicMock()

    @patch("manage_agenda.utils.moduleHtml.moduleHtml")
    def test_get_pages_from_urls(self, mock_module_html):
        # Setup mock
        mock_page = MagicMock()
        mock_module_html.return_value = mock_page
        mock_page.getPosts.return_value = ["post1", "post2"]

        urls = ["http://example.com"]

        # Execute
        page, posts = _get_pages_from_urls(self.args, urls)

        # Verify
        mock_page.setUrl.assert_called_with(urls)
        mock_page.setApiPosts.assert_called_once()
        self.assertEqual(posts, ["post1", "post2"])
        self.assertEqual(page, mock_page)

    @patch("manage_agenda.utils.moduleHtml.moduleHtml")
    def test_get_pages_from_urls_no_posts(self, mock_module_html):
        # Setup mock
        mock_page = MagicMock()
        mock_module_html.return_value = mock_page
        mock_page.getPosts.return_value = []

        urls = ["http://example.com"]

        # Execute
        page, posts = _get_pages_from_urls(self.args, urls)

        # Verify
        self.assertIsNone(posts)
        self.assertEqual(page, mock_page)

    @patch("manage_agenda.utils._get_pages_from_urls")
    @patch("manage_agenda.utils.moduleRules.moduleRules")
    @patch("manage_agenda.utils.reduce_html")
    @patch("manage_agenda.utils.write_file")
    @patch("manage_agenda.utils.print_first_10_lines")
    @patch("manage_agenda.utils._process_event_with_llm_and_calendar")
    def test_process_web_cli_success(
        self,
        mock_process_event,
        mock_print_lines,
        mock_write_file,
        mock_reduce_html,
        mock_module_rules,
        mock_get_pages
    ):
        # Setup mocks
        mock_page = MagicMock()
        mock_page.url = ["http://example.com/post1"]
        mock_page.getPostTitle.return_value = "Test Title"
        mock_get_pages.return_value = (mock_page, ["post_obj"])

        mock_rules = MagicMock()
        mock_module_rules.return_value = mock_rules

        mock_reduce_html.return_value = "reduced content"

        mock_process_event.return_value = (True, "Calendar Event Created")

        # Execute
        result = process_web_cli(self.args, self.model, urls=["http://example.com/post1"])

        # Verify
        self.assertTrue(result)
        mock_get_pages.assert_called_once()

        # Verify the fix: using api_src (mock_page) to access url and getPostTitle
        # If the code was using 'page' (undefined), it would crash here.
        # If it was using 'page' (defined but None/Wrong), it might fail assertions.

        # We implicitly verified the fix because the function ran successfully and we mocked the calls
        # that happen *after* accessing api_src.url[i].

        mock_page.getPostTitle.assert_called_with("post_obj")
        mock_reduce_html.assert_called_with("http://example.com/post1", "post_obj", force_refresh=False)

    @patch("manage_agenda.utils._get_pages_from_urls")
    @patch("manage_agenda.utils._get_links_from_notes")
    @patch("note_app.NoteManager")
    @patch("manage_agenda.utils._process_common_flow")
    def test_process_web_cli_deletes_note(
        self,
        mock_process_flow,
        mock_note_manager_class,
        mock_get_links,
        mock_get_pages
    ):
        # Setup
        url = "http://example.com/note_url"
        mock_get_links.return_value = {url: ["note_title"]}
        
        mock_manager = MagicMock()
        mock_note_manager_class.return_value = mock_manager
        
        mock_page = MagicMock()
        mock_get_pages.return_value = (mock_page, ["post_obj"])
        
        # Intercept _process_common_flow to trigger item_cleaner
        def side_effect(args, model, items, metadata_extractor, content_extractor, item_cleaner=None):
            if item_cleaner:
                item_cleaner("post_obj", 0, "post_id")
            return True
        mock_process_flow.side_effect = side_effect
        
        # Execute - simulating empty input to trigger _get_links_from_notes
        with patch("builtins.input", return_value=""):
            process_web_cli(self.args, self.model)
            
        # Verify
        mock_manager.delete_note.assert_called_with("note_title")

if __name__ == "__main__":
    unittest.main()
