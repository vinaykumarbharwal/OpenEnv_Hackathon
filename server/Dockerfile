FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY openenv_bug_triage/ ./openenv_bug_triage/
COPY server/ ./server/
COPY openenv.yaml .
COPY pyproject.toml .
COPY README.md .
COPY run.py .

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=5); print('OK')" || exit 1

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
