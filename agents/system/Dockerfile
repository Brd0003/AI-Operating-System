FROM python:3.11-slim
WORKDIR /app

# Copy the requirements file explicitly
COPY agents/system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the specialized worker agents and the core system agent
COPY agents/ ./agents/

# Copy the OS memory layer (Redis checkpointer & Qdrant SSE)
COPY memory/ ./memory/

# Tell Python that /app is the root path so all cross-folder imports work natively
ENV PYTHONPATH=/app

# Start the harness
CMD ["python", "agents/system/harness.py"]
