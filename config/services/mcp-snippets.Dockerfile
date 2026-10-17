FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install uv via official installer — puts binary at /root/.local/bin/uv
# Do NOT set UV_PYTHON_PREFERENCE=only-system; uvx needs to create isolated envs
RUN apk add --no-cache curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

EXPOSE 8000
ENTRYPOINT ["catatonit", "--", "mcp-proxy"]
# --pass-environment is REQUIRED — without it, mcp-proxy spawns uvx with an
# empty env (no PATH, no HOME, no UV_CACHE_DIR), causing immediate subprocess
# crash and McpError: Connection closed on every connection attempt.
# mcp-proxy serves both /sse and /mcp paths simultaneously; LiteLLM uses /mcp.
CMD ["--pass-environment", "--port", "8000", "--host", "0.0.0.0", "--", \
     "uvx", "mcp-code-snippets"]
