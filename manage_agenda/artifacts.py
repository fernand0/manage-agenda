"""Structured persistence for the partial results of a run.

Every artifact of a run lives under one per-run directory, keeping the input
directories clean and making whole runs easy to inspect or delete::

    <base>/runs/<timestamp>/posts/<post_id>/response.<model>.txt
    <base>/runs/<timestamp>/posts/<post_id>/extracted.<model>.json   (-v only)
    <base>/runs/<timestamp>/posts/<post_id>/prompt.txt               (-v only)
    <base>/runs/<timestamp>/posts/<post_id>/events.json
    <base>/runs/<timestamp>/posts/<post_id>/failure.json

Deliverables for ``--output=file`` default to ``./events/`` under the current
directory and can be redirected with ``--output-dir``.

``<base>`` defaults to ``~/.local/share/manage-agenda``; tests redirect it by
patching ``artifacts.BASE_DIR``.
"""

import json
import logging
import re
from pathlib import Path

from manage_agenda.config import DATA_DIR, RUN_START_TIME

BASE_DIR = DATA_DIR / "runs"
DEFAULT_DELIVERABLE_DIR = Path("events")

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def run_dir() -> Path:
    """Directory holding every artifact written by the current run."""
    return Path(BASE_DIR) / RUN_START_TIME


def _safe(component) -> str:
    """Reduce an externally derived id (post id, model name) to a filename-safe string."""
    text = _UNSAFE_CHARS.sub("_", str(component)).strip("._")
    return text[:80] or "unknown"


def _write(path: Path, content: str):
    """Write one artifact, creating parent directories; None on failure."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as error:
        logging.error("Error writing artifact %s: %s", path, error)
        return None
    logging.info("Artifact written: %s", path)
    return path


def save_response(model_name, post_id, response):
    """Persist the raw LLM response: the one artifact that cannot be regenerated."""
    path = run_dir() / "posts" / _safe(post_id) / f"response.{_safe(model_name)}.txt"
    return _write(path, response)


def save_extracted(model_name, post_id, vcal_json, verbose=False):
    """Persist the parsed event JSON; only written in verbose mode."""
    if not verbose:
        return None
    path = run_dir() / "posts" / _safe(post_id) / f"extracted.{_safe(model_name)}.json"
    return _write(path, json.dumps(vcal_json, indent=2))


def save_prompt(post_id, prompt, verbose=False):
    """Persist the prompt sent to the LLM; only written in verbose mode."""
    if not verbose:
        return None
    return _write(run_dir() / "posts" / _safe(post_id) / "prompt.txt", prompt)


def save_events(post_id, events):
    """Persist the final normalized events of a post."""
    path = run_dir() / "posts" / _safe(post_id) / "events.json"
    return _write(path, json.dumps(events, indent=2))


def save_failure(post_id, model_name, reason):
    """Persist why a post could not be processed."""
    payload = {"post_id": str(post_id), "model": str(model_name), "reason": str(reason)}
    path = run_dir() / "posts" / _safe(post_id) / "failure.json"
    return _write(path, json.dumps(payload, indent=2))


def save_deliverable(post_id, idx, event, output_dir=None, model_name=None):
    """Persist a published event for runs with file output."""
    base = Path(output_dir) if output_dir else Path.cwd() / DEFAULT_DELIVERABLE_DIR
    name = f"{_safe(post_id)}_{idx}"
    if model_name:
        name = f"{name}.{_safe(model_name)}"
    return _write(base / f"{name}.json", json.dumps(event, indent=2))
