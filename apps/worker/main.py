import os
import time

from job import Job
from job_queue import job_queue

worker_id = os.getenv("WORKER_ID", "local-dev")

job = Job(
    id="job-001",
    type="test",
    status="queued",
    payload={"message": "Hello"}
)

job_queue.put(job)

print(f"Worker started: {worker_id}", flush=True)

while True:
    current_job = job_queue.get()

    print(f"Worker picked up job: {current_job}", flush=True)

    job_queue.task_done()

    time.sleep(10)