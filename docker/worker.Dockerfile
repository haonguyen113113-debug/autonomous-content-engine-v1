FROM python:3.12-slim

WORKDIR /app

COPY apps/worker/main.py /app/main.py
COPY apps/worker/job.py /app/job.py

CMD ["python", "main.py"]
