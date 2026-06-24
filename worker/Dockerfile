FROM python:3.11-slim

WORKDIR /app

# Copia o código antes do install: o pacote (ingestion/) precisa existir para o build.
COPY . .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Executa o pipeline de ingestão uma vez (em produção, agendar via cron/job).
CMD ["python", "-m", "ingestion.pipeline"]
