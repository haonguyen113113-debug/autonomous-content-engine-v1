FROM python:3.12-slim

WORKDIR /app

COPY apps/worker/main.py /app/main.py
COPY apps/worker/job.py /app/job.py
COPY apps/worker/job_queue.py /app/job_queue.py

CMD ["python", "main.py"]
