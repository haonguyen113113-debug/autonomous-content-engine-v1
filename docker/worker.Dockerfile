FROM python:3.12-slim

WORKDIR /app

COPY apps/worker/main.py /app/main.py

CMD ["python", "main.py"]
