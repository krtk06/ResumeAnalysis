FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    FASTEMBED_CACHE_PATH=/models/fastembed \
    EMBEDDER_CACHE_DIR=/models/fastembed \
    HF_HUB_OFFLINE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Bake the embedding model into the image so startup does not depend on
# Hugging Face availability. This keeps cold starts predictable on Oracle ARM.
# CI can disable this with --build-arg PRELOAD_MODEL=0.
ARG PRELOAD_MODEL=1
RUN if [ "$PRELOAD_MODEL" = "1" ]; then \
      python -c "from fastembed import TextEmbedding; m=TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2', cache_dir='/models/fastembed'); list(m.embed(['warmup']))"; \
    fi

RUN mkdir -p /models \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /models
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
