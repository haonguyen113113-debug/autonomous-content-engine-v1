import os
import time

worker_id = os.getenv("WORKER_ID", "local-dev")

print(f"Worker started: {worker_id}")

while True:
    print("Worker is alive.")
    time.sleep(10)
