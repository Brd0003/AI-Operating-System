FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN uv pip install --system --no-cache-dir fastmcp qdrant-client mcp uvicorn fastapi pydantic httpx

COPY memory/ ./memory/

ENV FASTMCP_SERVER_HOST=0.0.0.0
ENV FASTMCP_SERVER_PORT=8000

EXPOSE 8000

CMD ["python", "memory/qdrant/explicit.py"]