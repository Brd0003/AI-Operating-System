# 1. Grab your compiled Rust binary from the dedicated image
FROM mcp/rust-mcp-filesystem:latest AS binary

# 2. Build the main System Agent image
FROM python:3.11-slim
WORKDIR /app

# 3. Install system dependencies (Node.js/npm for GitHub MCP, curl for utilities)
RUN apt-get update && apt-get install -y \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 4. Install uv (for Qdrant MCP)
RUN pip install --no-cache-dir uv

# Install mcp-code-snippets globally
RUN pip install --no-cache-dir mcp-code-snippets

# Copy the proxy configuration into the container from the qdrant kernel folder
COPY kernel/qdrant/mcp_proxy.json /app/mcp_proxy.json

# 5. Bring in the Rust Filesystem binary
COPY --from=binary /rust-mcp-filesystem /usr/local/bin/rust-mcp-filesystem
RUN chmod +x /usr/local/bin/rust-mcp-filesystem

# 6. Install Python requirements
COPY agents/system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy the specialized worker agents and the core system agent
COPY agents/ ./agents/

# 8. Copy the OS memory layer
COPY memory/ ./memory/

# 9. Tell Python that /app is the root path so all cross-folder imports work natively
ENV PYTHONPATH=/app

# 10. Start the harness
CMD ["python", "agents/system/harness.py"]