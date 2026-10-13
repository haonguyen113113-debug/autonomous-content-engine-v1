import os
import time
from pathlib import Path

try:  # package context: python -m apps.worker.main (incl. Docker image)
    from apps.worker.job import Job
    from apps.worker.runner import process_job
    from apps.worker.queue_store import claim_job, finish_job, recover_stale_claims
except ImportError:  # flat context: python main.py inside apps/worker/
    from job import Job
    from runner import process_job
    from queue_store import claim_job, finish_job, recover_stale_claims


def _paths() -> tuple[Path, Path]:
    root = Path(os.environ.get("ENGINE_ROOT", ".")).resolve()
    return root, root / "runtime/engine.db"


def main() -> None:
    worker_id = os.getenv("WORKER_ID", "local-dev")
    try:
        poll_seconds = max(1, int(os.getenv("WORKER_POLL_SECONDS", "15")))
    except (TypeError, ValueError):
        poll_seconds = 15
    root, db_path = _paths()
    recovered = recover_stale_claims(root, worker_id)
    if recovered:
        print(f"Worker recovered {len(recovered)} stale claim(s).", flush=True)
    print(f"Worker started: {worker_id} (root: {root})", flush=True)
    idle_polls = 0
    while True:
        try:
            claimed = claim_job(root, worker_id)
        except Exception as error:  # noqa: BLE001 - worker must stay alive
            print(f"Worker queue error: {error}", flush=True)
            time.sleep(poll_seconds)
            continue
        if claimed is None:
            idle_polls += 1
            if idle_polls % 20 == 0:
                recover_stale_claims(root, worker_id)
            time.sleep(poll_seconds)
            continue
        idle_polls = 0
        job = Job(id=str(claimed.get("id", "?")),
                  type=str(claimed.get("type", "?")),
                  status="claimed",
                  payload=claimed.get("payload") or {})
        try:
            result = process_job(root, db_path, job)
            finish_job(root, job.id, "done", result=result)
            print(f"Worker finished job {job.id}: {result}", flush=True)
        except Exception as error:  # noqa: BLE001 - worker must stay alive
            try:
                finish_job(root, job.id, "failed", error=str(error)[:500])
            except Exception as finish_error:  # noqa: BLE001 - never lose the cause
                print(f"Worker could not record failure for {job.id}: {finish_error}",
                      flush=True)
            print(f"Worker job failed: {error}", flush=True)


if __name__ == "__main__":
    main()
