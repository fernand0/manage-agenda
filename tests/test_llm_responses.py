from pathlib import Path

import pytest

from manage_agenda.extraction import get_event_from_llm

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "llm_responses"
FIXTURE_CASES = [
    ("single_event.json", ["2030-01-15T00:00:00"]),
    ("multiple_events.txt", ["2030-02-10", "2030-03-11"]),
    ("reasoning_before_json.txt", ["2030-04-12 09:00:00"]),
    ("single_quotes_response.txt", ["2030-05-16 09:00:00"]),
    ("truncated_response.txt", None),
]


class FixtureModel:
    model_name = "fixture"

    def __init__(self, response):
        self.response = response

    def generate_text(self, prompt):
        return self.response


@pytest.mark.parametrize(
    ("fixture_name", "expected_start_dates"),
    FIXTURE_CASES,
)
def test_parses_llm_response_fixture(fixture_name, expected_start_dates, monkeypatch):
    response = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    monkeypatch.setattr("manage_agenda.extraction.write_file", lambda *args: None)

    event, _, _ = get_event_from_llm(
        FixtureModel(response), "Extract calendar events", fixture_name
    )

    if expected_start_dates is None:
        assert event is None
        return

    events = event if isinstance(event, tuple) else (event,)
    assert [item["start"]["dateTime"] for item in events] == expected_start_dates


def test_every_response_fixture_has_a_test_case():
    fixture_files = {path.name for path in FIXTURES_DIR.iterdir() if path.is_file()}
    case_files = {fixture_name for fixture_name, _ in FIXTURE_CASES}

    assert fixture_files == case_files
