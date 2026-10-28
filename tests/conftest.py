import pytest

@pytest.fixture(autouse=True)
def isolated_log_file(monkeypatch, tmp_path):
    """
    Fixture to ensure that all tests use an isolated log file in a temporary directory.
    This prevents tests from failing due to environment-specific log file paths.
    """
    log_file_path = tmp_path / "test_manage_agenda.log"
    monkeypatch.setenv("LOG_FILE", str(log_file_path))


@pytest.fixture(autouse=True)
def isolated_artifacts_dir(monkeypatch, tmp_path):
    """
    Fixture to redirect all run artifacts to a temporary directory.
    This prevents tests from writing to the user's real data directory.
    """
    from manage_agenda import artifacts

    monkeypatch.setattr(artifacts, "BASE_DIR", tmp_path / "runs")
    return artifacts.run_dir()
