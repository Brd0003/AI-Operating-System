FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv, mcp-server-qdrant, fastembed, and mcp-proxy via pip to ensure binaries are in PATH
RUN pip install --no-cache-dir uv && \
    uv pip install --system mcp-server-qdrant fastembed qdrant-client mcp-proxy

ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"

# Pre-download the embedding model at build time so the container never needs
# to reach HuggingFace or GCS at runtime (both blocked by egress policy).
# fastembed caches to ~/.cache/fastembed by default; baking it into the image
# avoids the [Errno 21] Is a directory / download-fail restart loop.
ENV FASTEMBED_CACHE_PATH=/root/.cache/fastembed
RUN python - <<'EOF'
from fastembed import TextEmbedding
# Triggers download + caches the model inside the image layer
_ = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
EOF

EXPOSE 8000
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--port", "8000", "--host", "0.0.0.0", "--", "mcp-server-qdrant"]