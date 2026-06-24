FROM python:3.11-slim

WORKDIR /app

# Copia o código antes do install: o pacote (app/) precisa existir para o build
# (packages declarado em pyproject.toml [tool.setuptools]).
COPY . .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
