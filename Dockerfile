# Imagen mínima para ejecutar repo_scorecard y app de prueba
FROM python:3.11-slim

WORKDIR /app
COPY repo_scorecard.py .
COPY app_prueba/ app_prueba/
COPY pyproject.toml .

RUN pip install --no-cache-dir pytest

CMD ["python", "repo_scorecard.py", "--path", ".", "--out", "text"]
