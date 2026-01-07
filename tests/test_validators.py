import sys
import unittest

sys.path.append(".")

from manage_agenda.exceptions import ValidationError
from manage_agenda.validators import (
    sanitize_filename,
    validate_api_key,
    validate_datetime_iso,
    validate_email,
    validate_event_dict,
    validate_llm_response,
    validate_timezone,
    validate_url,
)


class TestValidators(unittest.TestCase):
    def test_validate_email_valid(self):
        """Test valid email addresses."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "123@test.com",
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertTrue(validate_email(email))

    def test_validate_email_invalid(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "invalid",
            "@example.com",
            "user@",
            "user @example.com",
            "",
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertFalse(validate_email(email))

    def test_validate_url_valid(self):
        """Test valid URLs."""
        valid_urls = [
            "http://example.com",
            "https://www.example.com",
            "https://example.com/path/to/page",
            "http://example.com:8080/page",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(validate_url(url))

    def test_validate_url_invalid(self):
        """Test invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "http://",
            "",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(validate_url(url))

    def test_validate_timezone_valid(self):
        """Test valid timezone names."""
        valid_timezones = [
            "Europe/Berlin",
            "America/New_York",
            "UTC",
            "Asia/Tokyo",
        ]
        for tz in valid_timezones:
            with self.subTest(tz=tz):
                self.assertTrue(validate_timezone(tz))

    def test_validate_timezone_invalid(self):
        """Test invalid timezone names."""
        invalid_timezones = [
            "Invalid/Timezone",
            "Mars/City",
        ]
        for tz in invalid_timezones:
            with self.subTest(tz=tz):
                self.assertFalse(validate_timezone(tz))

    def test_validate_datetime_iso_valid(self):
        """Test valid ISO datetime strings."""
        valid_datetimes = [
            "2024-01-15T10:30:00",
            "2024-12-31T23:59:59",
        ]
        for dt in valid_datetimes:
            with self.subTest(dt=dt):
                self.assertTrue(validate_datetime_iso(dt))

    def test_validate_datetime_iso_invalid(self):
        """Test invalid ISO datetime strings."""
        invalid_datetimes = [
            "2024-13-01T10:30:00",  # Invalid month
            "2024-01-32T10:30:00",  # Invalid day
            "not-a-date",
            "",
        ]
        for dt in invalid_datetimes:
            with self.subTest(dt=dt):
                self.assertFalse(validate_datetime_iso(dt))

    def test_sanitize_filename_valid(self):
        """Test sanitizing valid filenames."""
        test_cases = [
            ("valid_file.txt", "valid_file.txt"),
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("file/with/slashes.txt", "filewithslashes.txt"),  # Slashes removed
            ("file:with:colons.txt", "filewithcolons.txt"),  # Colons removed
        ]
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_filename(input_name)
                self.assertEqual(result, expected)

    def test_validate_api_key_valid(self):
        """Test validating API keys."""
        # API key must be at least 20 characters
        self.assertTrue(validate_api_key("a" * 25, "gemini"))

    def test_validate_api_key_invalid(self):
        """Test invalid API keys."""
        self.assertFalse(validate_api_key(None, "gemini"))
        self.assertFalse(validate_api_key("", "gemini"))
        self.assertFalse(validate_api_key("short", "gemini"))  # Too short

    def test_validate_event_dict_valid(self):
        """Test validating valid event dictionary."""
        valid_event = {
            "summary": "Test Event",
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(valid_event)
        self.assertEqual(len(errors), 0)

    def test_validate_event_dict_missing_fields(self):
        """Test validating event dict with missing fields."""
        invalid_event = {
            "summary": "Test Event",
        }
        errors = validate_event_dict(invalid_event)
        self.assertGreater(len(errors), 0)

    def test_validate_event_dict_missing_summary(self):
        """Test event without summary."""
        event = {
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Event must have a summary", str(errors))

    def test_validate_event_dict_invalid_start_datetime(self):
        """Test event with invalid start datetime."""
        event = {
            "summary": "Test",
            "start": {"dateTime": "invalid-date"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Invalid start dateTime", str(errors))

    def test_validate_event_dict_invalid_end_datetime(self):
        """Test event with invalid end datetime."""
        event = {
            "summary": "Test",
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "invalid-date"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Invalid end dateTime", str(errors))

    def test_validate_event_dict_invalid_start_timezone(self):
        """Test event with invalid start timezone."""
        event = {
            "summary": "Test",
            "start": {"dateTime": "2024-01-15T10:00:00", "timeZone": "Invalid/TZ"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Invalid start timezone", str(errors))

    def test_validate_event_dict_invalid_end_timezone(self):
        """Test event with invalid end timezone."""
        event = {
            "summary": "Test",
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "2024-01-15T11:00:00", "timeZone": "Invalid/TZ"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Invalid end timezone", str(errors))

    def test_validate_event_dict_end_before_start(self):
        """Test event with end time before start time."""
        event = {
            "summary": "Test",
            "start": {"dateTime": "2024-01-15T11:00:00"},
            "end": {"dateTime": "2024-01-15T10:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("end time must be after start time", str(errors))

    def test_validate_event_dict_description_too_long(self):
        """Test event with description exceeding limit."""
        event = {
            "summary": "Test",
            "description": "x" * 9000,  # More than 8192 chars
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Description too long", str(errors))

    def test_validate_event_dict_summary_too_long(self):
        """Test event with summary exceeding limit."""
        event = {
            "summary": "x" * 1100,  # More than 1024 chars
            "start": {"dateTime": "2024-01-15T10:00:00"},
            "end": {"dateTime": "2024-01-15T11:00:00"},
        }
        errors = validate_event_dict(event)
        self.assertIn("Summary too long", str(errors))

    def test_validate_llm_response_valid_json(self):
        """Test validating valid LLM JSON response."""
        response = '{"key": "value", "number": 42}'
        result = validate_llm_response(response)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "value")

    def test_validate_llm_response_with_markdown(self):
        """Test LLM response wrapped in markdown code block."""
        response = '```json\n{"key": "value"}\n```'
        result = validate_llm_response(response)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "value")

    def test_validate_llm_response_with_plain_markdown(self):
        """Test LLM response wrapped in plain code block."""
        response = '```\n{"key": "value"}\n```'
        result = validate_llm_response(response)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "value")

    def test_validate_llm_response_empty(self):
        """Test LLM response with empty string."""
        with self.assertRaises(ValidationError) as context:
            validate_llm_response("")
        self.assertIn("empty response", str(context.exception))

    def test_validate_llm_response_invalid_json(self):
        """Test LLM response with invalid JSON."""
        with self.assertRaises(ValidationError) as context:
            validate_llm_response("{invalid json}")
        self.assertIn("Invalid JSON", str(context.exception))

    def test_validate_llm_response_not_dict(self):
        """Test LLM response that's not a dictionary."""
        with self.assertRaises(ValidationError) as context:
            validate_llm_response('["array", "not", "dict"]')
        self.assertIn("must be a JSON object", str(context.exception))

    def test_sanitize_filename_long(self):
        """Test sanitizing filename that exceeds max length."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 255)


if __name__ == "__main__":
    unittest.main()
