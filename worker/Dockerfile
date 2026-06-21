FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY . .

# Executa o pipeline de ingestão uma vez (em produção, agendar via cron/job).
CMD ["python", "-m", "ingestion.pipeline"]
