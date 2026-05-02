FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt

# Pre-pull both local models so the first request is fast.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_small-v2.1')"

COPY code code
COPY agent agent

ENV PYTHONUNBUFFERED=1 \
    LEARNING_SERVER_HOST=0.0.0.0 \
    LEARNING_SERVER_PORT=4180

EXPOSE 4180

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:4180/stats || exit 1

CMD ["python", "-m", "agent.learning.server"]
