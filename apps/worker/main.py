import os
import time
from pathlib import Path
from queue import Empty

from job import Job
from job_queue import job_queue

try:
    from apps.worker.runner import process_job
except ImportError:  # running inside apps/worker as cwd
    from runner import process_job


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
    print(f"Worker started: {worker_id} (root: {root})", flush=True)
    while True:
        try:
            job = job_queue.get(timeout=poll_seconds)
        except Empty:
            continue
        try:
            if isinstance(job, Job):
                result = process_job(root, db_path, job)
                job.status = "done"
                print(f"Worker finished job {job.id}: {result}", flush=True)
            else:
                print(f"Worker dropped non-job payload: {job!r}", flush=True)
        except Exception as error:  # noqa: BLE001 - worker must stay alive
            if isinstance(job, Job):
                job.status = "failed"
            print(f"Worker job failed: {error}", flush=True)
        finally:
            job_queue.task_done()


if __name__ == "__main__":
    main()
