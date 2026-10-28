"""Tests for the per-run artifacts layout."""

import json

from manage_agenda import artifacts


def test_save_response_layout():
    path = artifacts.save_response("qwen:4b", "post-1", "raw reply")

    expected = artifacts.run_dir() / "posts" / "post-1" / "response.qwen_4b.txt"
    assert path == expected
    assert expected.read_text(encoding="utf-8") == "raw reply"


def test_save_events_writes_final_events():
    events = [{"summary": "Test", "start": {"dateTime": "2026-10-28 10:00:00"}}]

    path = artifacts.save_events("post-1", events)

    assert path == artifacts.run_dir() / "posts" / "post-1" / "events.json"
    assert json.loads(path.read_text(encoding="utf-8")) == events


def test_save_failure_records_reason():
    path = artifacts.save_failure("post-1", "qwen:4b", "JsonError")

    assert path.name == "failure.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {"post_id": "post-1", "model": "qwen:4b", "reason": "JsonError"}


def test_verbose_only_artifacts_are_gated():
    assert artifacts.save_prompt("post-1", "prompt", verbose=False) is None
    assert artifacts.save_extracted("m", "post-1", {}, verbose=False) is None
    assert not (artifacts.run_dir() / "posts").exists()

    assert artifacts.save_prompt("post-1", "prompt", verbose=True) is not None
    assert artifacts.save_extracted("m", "post-1", {"a": 1}, verbose=True) is not None
    assert (artifacts.run_dir() / "posts" / "post-1" / "prompt.txt").exists()
    assert (artifacts.run_dir() / "posts" / "post-1" / "extracted.m.json").exists()


def test_save_deliverable_defaults_to_documents_events_dir(monkeypatch, tmp_path):
    home = tmp_path / "home"
    documents_dir = home / "Documents"
    documents_dir.mkdir(parents=True)
    monkeypatch.setattr(artifacts.Path, "home", lambda: home)

    path = artifacts.save_deliverable("post-1", 2, {"summary": "Test"})

    assert path == documents_dir / "events" / "post-1_2.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"summary": "Test"}


def test_save_deliverable_falls_back_when_documents_dir_is_unavailable(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setattr(artifacts.Path, "home", lambda: home)
    monkeypatch.setattr(artifacts, "DATA_DIR", tmp_path / "data")

    path = artifacts.save_deliverable("post-1", 2, {"summary": "Test"})

    assert path == tmp_path / "data" / "events" / "post-1_2.json"


def test_save_deliverable_honors_output_dir_and_model(tmp_path):
    path = artifacts.save_deliverable(
        "post-1", 1, {"summary": "Test"}, output_dir=tmp_path / "out", model_name="qwen:4b"
    )

    assert path == tmp_path / "out" / "post-1_1.qwen_4b.json"
    assert path.exists()


def test_unsafe_ids_stay_inside_the_run_dir():
    artifacts.save_response("m", "../../../secrets", "data")
    artifacts.save_events("a/b c:d", [])

    written = [p for p in artifacts.run_dir().rglob("*") if p.is_file()]
    assert len(written) == 2
    assert all(p.parent.parent == artifacts.run_dir() / "posts" for p in written)


def test_empty_ids_fall_back_to_unknown():
    path = artifacts.save_response("m", "", "data")

    assert path.parent.name == "unknown"
