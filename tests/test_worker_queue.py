"""File-backed worker queue: enqueue/claim/finish/recover/list."""

import json

import pytest

from apps.worker import queue_store
from apps.worker.queue_store import (
    claim_job,
    enqueue_job,
    finish_job,
    list_jobs,
    recover_stale_claims,
    validate_draft_payload,
)


def _job(topic="Derby thanh Manchester toi nay"):
    return {"topic": topic, "story_form": "hook", "evidence": "",
            "content_type": "short", "colorway": "san-dem"}


def test_enqueue_claim_finish_roundtrip(tmp_path):
    record = enqueue_job(tmp_path, "draft", _job())
    assert record["status"] == "queued" and record["attempts"] == 0
    assert (tmp_path / "runtime/queue/queued" / f"{record['id']}.json").is_file()
    claimed = claim_job(tmp_path, "worker-a")
    assert claimed and claimed["id"] == record["id"]
    assert claimed["status"] == "claimed" and claimed["attempts"] == 1
    assert claimed["worker_id"] == "worker-a"
    assert claim_job(tmp_path, "worker-b") is None
    done = finish_job(tmp_path, record["id"], "done", result={"run_id": "a" * 12})
    assert done["status"] == "done"
    assert done["result"] == {"run_id": "a" * 12}
    assert (tmp_path / "runtime/queue/done" / f"{record['id']}.json").is_file()


def test_claim_empty_queue_returns_none(tmp_path):
    assert claim_job(tmp_path, "worker-a") is None


def test_enqueue_rejects_bad_input_without_writing(tmp_path):
    with pytest.raises(ValueError, match="Unsupported job type"):
        enqueue_job(tmp_path, "publish", _job())
    with pytest.raises(ValueError, match="4-500"):
        enqueue_job(tmp_path, "draft", _job(topic="x"))
    with pytest.raises(ValueError, match="short or long"):
        enqueue_job(tmp_path, "draft", _job() | {"content_type": "huge"})
    assert not (tmp_path / "runtime/queue").exists()


def test_validate_clamps_and_defaults():
    clean = validate_draft_payload({"topic": "  Tran derby toi nay  ", "max_attempts": 99})
    assert clean["topic"] == "Tran derby toi nay"
    assert clean["content_type"] == "short" and clean["colorway"] == "san-dem"
    assert clean["max_attempts"] == queue_store.MAX_ATTEMPTS_CAP
    with pytest.raises(ValueError, match="must be an object"):
        validate_draft_payload("nope")


def test_finish_requires_claimed(tmp_path):
    with pytest.raises(ValueError, match="No claimed job"):
        finish_job(tmp_path, "deadbeef1234", "done")
    with pytest.raises(ValueError, match="done or failed"):
        finish_job(tmp_path, "deadbeef1234", "maybe")


def test_stale_claim_recovers_then_exhausts(tmp_path):
    record = enqueue_job(tmp_path, "draft", _job() | {"max_attempts": 1})
    claimed = claim_job(tmp_path, "worker-a")
    assert claimed is not None
    path = tmp_path / "runtime/queue/claimed" / f"{record['id']}.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["claimed_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(stored), encoding="utf-8")
    recovered = recover_stale_claims(tmp_path, "worker-b", stale_seconds=60)
    assert len(recovered) == 1 and recovered[0]["status"] == "failed"
    assert "exhausted" in (recovered[0]["error"] or "")


def test_stale_claim_requeues_when_attempts_remain(tmp_path):
    record = enqueue_job(tmp_path, "draft", _job())
    assert claim_job(tmp_path, "worker-a") is not None
    path = tmp_path / "runtime/queue/claimed" / f"{record['id']}.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["claimed_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(stored), encoding="utf-8")
    recovered = recover_stale_claims(tmp_path, "worker-b", stale_seconds=60)
    assert recovered[0]["status"] == "queued"
    again = claim_job(tmp_path, "worker-b")
    assert again and again["attempts"] == 2


def test_list_jobs_overview(tmp_path):
    first = enqueue_job(tmp_path, "draft", _job())
    second = enqueue_job(tmp_path, "draft", _job("Mot tran cau dinh doat khac"))
    claimed = claim_job(tmp_path, "worker-a")
    assert claimed is not None
    other = second["id"] if claimed["id"] == first["id"] else first["id"]
    finish_job(tmp_path, claimed["id"], "failed", error="boom")
    jobs = list_jobs(tmp_path)
    by_id = {item["id"]: item["status"] for item in jobs}
    assert by_id == {claimed["id"]: "failed", other: "queued"}
