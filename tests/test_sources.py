import datetime
import sys
import unittest
from collections import namedtuple
from email.utils import formatdate
from unittest.mock import MagicMock, patch

from manage_agenda.sources import Args, list_folder, process_email_cli


class TestProcessEmailCli(unittest.TestCase):
    def setUp(self):
        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.extraction.select_api")
    @patch("manage_agenda.sources.select_api")
    @patch("manage_agenda.sources._get_emails_from_folder")
    @patch("manage_agenda.extraction.select_calendar")
    @patch("manage_agenda.extraction.write_file")
    @patch("manage_agenda.sources.write_file")
    def test_process_email_cli_success(
        self,
        mock_source_write_file,
        mock_write_file,
        mock_select_calendar,
        mock_get_emails_from_folder,
        mock_select_api_source,
        mock_select_api_destination,
    ):
        args = self.Args(
            interactive=False,
            delete=None,
            source="gemini",
            verbose=False,
            destination="",
            text="",
        )
        mock_model = MagicMock()
        mock_model.generate_text.return_value = """```json
{"summary": "Test Event", "start": {"dateTime": "2024-01-01T10:00:00"}, "end": {"dateTime": "2024-01-01T11:00:00"}}
```"""
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "Label_0"}]
        mock_api_src.getPosts.return_value = ["post_id"]
        mock_api_src.getPostId.return_value = "post_id"
        mock_api_src.getPostDate.return_value = formatdate(
            timeval=datetime.datetime.now().timestamp(), localtime=True
        )
        mock_api_src.getPostTitle.return_value = "Test title"
        mock_api_src.getPostBody.return_value = "Test Body"

        mock_get_emails_from_folder.return_value = ["post_id"]

        mock_api_dst = MagicMock()
        mock_select_api_source.return_value = mock_api_src
        mock_select_api_destination.return_value = mock_api_dst
        mock_select_calendar.return_value = "primary"

        process_email_cli(args, mock_model)

        self.assertEqual(mock_model.generate_text.call_count, 2)
        mock_source_write_file.assert_called_once()
        self.assertEqual(mock_write_file.call_count, 9)
        mock_select_calendar.assert_called_once()
        mock_api_dst.publishPost.assert_called_once()
        mock_api_src.modifyLabels.assert_called_once()

    @patch("manage_agenda.sources.select_api")
    @patch("manage_agenda.sources._get_emails_from_folder")
    def test_process_email_cli_fallback_selects_any_email_service(
        self, mock_get_emails_from_folder, mock_select_api
    ):
        args = self.Args(
            interactive=False,
            delete=False,
            source=None,
            verbose=False,
            destination="",
            text="",
        )
        rules = MagicMock()
        mock_get_emails_from_folder.return_value = []

        process_email_cli(args, MagicMock(), rules=rules)

        mock_select_api.assert_called_once_with(args, "email", rules=rules)

    @patch("manage_agenda.sources.moduleRules")
    @patch("manage_agenda.sources._get_emails_from_folder")
    def test_process_email_cli_selected_source_loads_default_rules(
        self, mock_get_emails_from_folder, mock_module_rules
    ):
        args = self.Args(
            interactive=False,
            delete=False,
            source=None,
            verbose=False,
            destination="",
            text="",
        )
        rules = mock_module_rules.from_config.return_value
        source_details = {"service": "imap"}
        rules.more = {"mail-account": source_details}
        mock_get_emails_from_folder.return_value = []

        process_email_cli(args, MagicMock(), selected_source="mail-account")

        rules.readConfigSrc.assert_called_once_with("", "mail-account", source_details)

        self.Args = namedtuple(
            "args",
            ["interactive", "delete", "source", "verbose", "destination", "text"],
        )

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_events_from_calendar")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gcalendar_folder_with_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        mock_api_src = MagicMock()
        events = ["post1", "post2"]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = events
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gcalendar")
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gcalendar", title="Select calendar account"
        )
        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, events)

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_events_from_calendar")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gcalendar_folder_without_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = None
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gcalendar")
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gcalendar", title="Select calendar account"
        )
        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_emails_from_folder")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gmail_folder_with_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = ["post1", "post2"]
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gmail")
        mock_module_rules.from_config.assert_called_once()
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, ["post1", "post2"])

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_emails_from_folder")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gmail_folder_without_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = None
        args = self.Args(
            interactive=False,
            delete=False,
            source="any",
            verbose=False,
            destination="",
            text="",
        )
        list_folder(args, "gmail")
        mock_module_rules.from_config.assert_called_once()
        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)


class TestSourceUtilities(unittest.TestCase):
    def test_print_first_10_lines_short(self):
        """Test print_first_10_lines with content shorter than 10 lines."""
        import io

        from manage_agenda.sources import print_first_10_lines

        content = "line1\nline2\nline3"
        captured_output = io.StringIO()
        sys.stdout = captured_output
        print_first_10_lines(content, "test")
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("line1", output)
        self.assertIn("line2", output)
        self.assertIn("line3", output)

    def test_print_first_10_lines_long(self):
        """Test print_first_10_lines with content longer than 10 lines."""
        import io

        from manage_agenda.sources import print_first_10_lines

        content = "\n".join([f"line{i}" for i in range(20)])
        captured_output = io.StringIO()
        sys.stdout = captured_output
        print_first_10_lines(content)
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        self.assertIn("line0", output)
        self.assertIn("line9", output)
        self.assertNotIn("line10", output)

    @patch("manage_agenda.sources.moduleRules")
    def test_get_add_sources(self, mock_module_rules):
        """Test get_add_sources returns correct sources."""
        from manage_agenda.sources import get_add_sources

        mock_rules = MagicMock()
        mock_rules.selectRule.return_value = ["gmail1", "imap1"]
        mock_module_rules.from_config.return_value = mock_rules

        sources = get_add_sources(rules=mock_rules)

        print(f"Sources: {sources}")
        self.assertIn("gmail1", sources[0])
        self.assertIn("imap1", sources[0])
        self.assertIn("web", str(sources[1]))
        self.assertIn("http", str(sources[1]))
        self.assertIn(("text", "set", "(enter filenames or leave empty)"), sources[1])

    def test_get_post_datetime_and_diff_timestamp(self):
        """Test _get_post_datetime_and_diff with timestamp."""
        from manage_agenda.sources import _get_post_datetime_and_diff

        timestamp = str(int(datetime.datetime.now().timestamp() * 1000))
        post_datetime, time_diff = _get_post_datetime_and_diff(timestamp)

        self.assertIsInstance(post_datetime, datetime.datetime)
        self.assertIsInstance(time_diff, datetime.timedelta)
        self.assertLess(time_diff.days, 1)

    def test_get_post_datetime_and_diff_email_format(self):
        """Test _get_post_datetime_and_diff with email date format."""
        from manage_agenda.sources import _get_post_datetime_and_diff

        email_date = formatdate(timeval=datetime.datetime.now().timestamp(), localtime=True)
        post_datetime, time_diff = _get_post_datetime_and_diff(email_date)

        self.assertIsInstance(post_datetime, datetime.datetime)
        self.assertIsInstance(time_diff, datetime.timedelta)

    @patch("builtins.input", return_value="y")
    def test_delete_email_interactive_confirm(self, mock_input):
        """Test _delete_email with interactive confirmation."""
        from manage_agenda.sources import _delete_email

        args = Args(interactive=True, delete=False)
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getChannel.return_value = "test_folder"
        mock_api_src.getLabels.return_value = [{"id": "label_1"}]

        _delete_email(args, mock_api_src, "post123", "test_source")

        mock_api_src.modifyLabels.assert_called_once()

    def test_delete_email_non_interactive_auto_confirms(self):
        """Test _delete_email automatically confirms outside interactive mode."""
        from manage_agenda.sources import _delete_email

        args = Args(interactive=False, delete=False)
        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getChannel.return_value = "test_folder"
        mock_api_src.getLabels.return_value = [{"id": "label_1"}]

        _delete_email(args, mock_api_src, "post123", "test_source")

        mock_api_src.modifyLabels.assert_called_once()
        mock_api_src.deletePostId.assert_not_called()

    def test_delete_email_imap(self):
        """Test _delete_email with IMAP service."""
        from manage_agenda.sources import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"

        _delete_email(args, mock_api_src, "post123", "test_source")

        mock_api_src.deletePostId.assert_called_once_with("post123")

    def test_delete_email_retry(self):
        """Test _delete_email with connection error and retry."""
        from manage_agenda.sources import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.deletePostId.side_effect = [Exception("Connection error"), None]

        with patch("manage_agenda.sources.moduleRules") as mock_module_rules:
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.from_config.return_value = mock_rules

            _delete_email(args, mock_api_src, "post123", "test_source")

            self.assertEqual(mock_api_src.deletePostId.call_count, 1)
            mock_rules.readConfigSrc.assert_called_once_with("", "test_source", {})
            mock_new_api_src.deletePostId.assert_called_once_with("post123")

    def test_delete_email_retry_failure(self):
        """Test _delete_email with connection error and all retries fail."""
        from manage_agenda.sources import _delete_email

        args = Args(interactive=False, delete=True)
        mock_api_src = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.deletePostId.side_effect = Exception("Connection error 1")

        with (
            patch("manage_agenda.sources.moduleRules") as mock_module_rules,
            patch("manage_agenda.sources.logging.error") as mock_logging_error,
        ):
            mock_rules = MagicMock()
            mock_rules.more.get.return_value = {}
            mock_new_api_src = MagicMock()
            mock_new_api_src.service = "imap"
            mock_new_api_src.deletePostId.side_effect = Exception("Connection error 2")
            mock_rules.readConfigSrc.return_value = mock_new_api_src
            mock_module_rules.from_config.return_value = mock_rules

            _delete_email(args, mock_api_src, "post123", "test_source")

            self.assertEqual(mock_api_src.deletePostId.call_count, 1)
            self.assertEqual(mock_new_api_src.deletePostId.call_count, 1)
            mock_logging_error.assert_called_once_with(
                "Could not delete email post123 after 2 attempts: Connection error 2"
            )

    def test_is_email_too_old_recent(self):
        """Test _is_email_too_old with recent email."""
        from manage_agenda.sources import _is_post_too_old

        args = Args(interactive=False, verbose=False)
        time_diff = datetime.timedelta(days=3)

        result = _is_post_too_old(args, time_diff)

        self.assertFalse(result)

    def test_is_email_too_old_old_non_interactive(self):
        """Test _is_email_too_old with old email, non-interactive."""
        from manage_agenda.sources import _is_post_too_old

        args = Args(interactive=False, verbose=True)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertTrue(result)

    @patch("builtins.input", return_value="n")
    def test_is_email_too_old_interactive_reject(self, mock_input):
        """Test _is_email_too_old with interactive rejection."""
        from manage_agenda.sources import _is_post_too_old

        args = Args(interactive=True, verbose=False)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertTrue(result)

    @patch("builtins.input", return_value="y")
    def test_is_email_too_old_interactive_accept(self, mock_input):
        """Test _is_email_too_old with interactive acceptance."""
        from manage_agenda.sources import _is_post_too_old

        args = Args(interactive=True, verbose=False)
        time_diff = datetime.timedelta(days=10)

        result = _is_post_too_old(args, time_diff)

        self.assertFalse(result)

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_events_from_calendar")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gcalendar_folder_with_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        """Test listing a calendar folder with posts."""
        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        events = [
            {"id": "1", "date": "2024-01-01", "title": "Event 1"},
            {"id": "2", "date": "2024-01-02", "title": "Event 2"},
        ]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = events

        list_folder(args, "gcalendar")

        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, events)

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_events_from_calendar")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gcalendar_folder_without_posts(
        self, mock_module_rules, mock_get_events, mock_display_posts
    ):
        """Test listing a calendar folder when no events are found."""
        args = Args(interactive=False, delete=False, verbose=False)
        mock_api_src = MagicMock()
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_events.return_value = None

        list_folder(args, "gcalendar")

        mock_get_events.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, None)

    def test_get_emails_from_folder_success(self):
        """Test _get_emails_from_folder with successful retrieval."""
        from manage_agenda.sources import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1", "name": "zAgenda"}]
        mock_api_src.getPosts.return_value = [{"id": "1"}, {"id": "2"}]

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertIsNotNone(posts)
        self.assertEqual(len(posts), 2)

    def test_get_emails_from_folder_no_label(self):
        """Test _get_emails_from_folder when the label does not exist."""
        import io

        from manage_agenda.sources import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = []

        captured_output = io.StringIO()
        sys.stdout = captured_output
        posts = _get_emails_from_folder(args, mock_api_src)
        sys.stdout = sys.__stdout__

        self.assertIsNone(posts)

    def test_get_emails_from_folder_no_imap_label(self):
        """Test _get_emails_from_folder when the IMAP label does not exist."""
        from manage_agenda.sources import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "imap"
        mock_api_src.getLabels.return_value = []

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertIsNone(posts)

    def test_get_emails_from_folder_no_posts(self):
        """Test _get_emails_from_folder when no posts found."""
        from manage_agenda.sources import _get_emails_from_folder

        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        mock_api_src.getClient.return_value = MagicMock()
        mock_api_src.service = "gmail"
        mock_api_src.getLabels.return_value = [{"id": "label1"}]
        mock_api_src.getPosts.return_value = []

        posts = _get_emails_from_folder(args, mock_api_src)

        self.assertEqual(posts, [])

    @patch("manage_agenda.sources.display_posts")
    @patch("manage_agenda.sources._get_emails_from_folder")
    @patch("manage_agenda.sources.moduleRules")
    def test_list_gmail_folder_with_posts(
        self, mock_module_rules, mock_get_emails, mock_display_posts
    ):
        """Test listing a Gmail folder with posts."""
        args = Args(interactive=False, delete=False, verbose=False)

        mock_api_src = MagicMock()
        posts = [{"id": "1"}, {"id": "2"}]
        mock_module_rules.from_config.return_value.selectRuleInteractive.return_value = mock_api_src
        mock_get_emails.return_value = posts

        list_folder(args, "gmail")

        mock_module_rules.from_config.return_value.selectRuleInteractive.assert_called_once_with(
            service="gmail", title="Select mail account"
        )
        mock_get_emails.assert_called_once_with(args, mock_api_src)
        mock_display_posts.assert_called_once_with(mock_api_src, posts)
