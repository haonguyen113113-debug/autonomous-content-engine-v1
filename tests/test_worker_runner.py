import time
from types import SimpleNamespace

import pytest

import apps.content_workflow as content_workflow
from apps.worker.runner import process_draft_job, process_job


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


def test_draft_retries_then_succeeds(monkeypatch, tmp_path, no_sleep):
    calls = []

    def flaky(root, db_path, topic, story_form, evidence="", content_type="short", colorway="match-night"):
        calls.append(topic)
        if len(calls) < 2:
            raise RuntimeError("Model endpoint unreachable: TimeoutError.")
        return {"run_id": "abcdef123456"}

    monkeypatch.setattr(content_workflow, "run_content_agent", flaky)
    result = process_draft_job(tmp_path, tmp_path / "db.sqlite",
                               {"topic": "T", "story_form": "s", "max_attempts": 3})
    assert result == {"status": "DONE", "run_id": "abcdef123456", "attempts": 2}


def test_draft_validation_error_does_not_retry(monkeypatch, tmp_path, no_sleep):
    calls = []

    def invalid(root, db_path, topic, story_form, evidence="", content_type="short", colorway="match-night"):
        calls.append(1)
        raise ValueError("Chủ đề cần dài từ 4 đến 500 ký tự.")

    monkeypatch.setattr(content_workflow, "run_content_agent", invalid)
    with pytest.raises(RuntimeError, match="after 1 attempt"):
        process_draft_job(tmp_path, tmp_path / "db.sqlite", {"topic": "x"})
    assert len(calls) == 1


def test_unknown_job_type_fails_loudly(tmp_path):
    with pytest.raises(ValueError, match="Unsupported job type"):
        process_job(tmp_path, tmp_path / "db.sqlite",
                    SimpleNamespace(type="publish", payload={}))
