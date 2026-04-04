FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and metadata
COPY openenv_bug_triage/ ./openenv_bug_triage/
COPY openenv.yaml .
COPY scripts/ ./scripts/
COPY README.md .

# Expose port for HF Spaces
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=5); print('OK')" || exit 1

# Default command for HF Spaces
CMD ["uvicorn", "openenv_bug_triage.app:app", "--host", "0.0.0.0", "--port", "7860"]
