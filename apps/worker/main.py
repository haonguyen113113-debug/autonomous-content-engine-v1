import os
import time

from job import Job

worker_id = os.getenv("WORKER_ID", "local-dev")

job = Job(
    id="job-001",
    type="test",
    status="queued",
    payload={"message": "Hello"}
)

print(f"Worker started: {worker_id}", flush=True)
print(f"Job created: {job}", flush=True)

while True:
    print("Worker is alive.", flush=True)
    time.sleep(10)