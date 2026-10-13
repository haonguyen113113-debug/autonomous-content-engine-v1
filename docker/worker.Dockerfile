FROM python:3.12-slim

WORKDIR /app

# Worker needs the engine packages it dispatches to (runner imports the
# content workflow), plus templates/taxonomy the workflow resolves.
COPY apps/ ./apps/
COPY template_foundation/ ./template_foundation/
COPY taxonomy.json ./
COPY data/ ./data/

ENV ENGINE_ROOT=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "apps.worker.main"]
