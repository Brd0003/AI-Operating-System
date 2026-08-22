FROM mcp/rust-mcp-filesystem:latest AS binary

FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir mcp fastapi uvicorn pydantic

COPY --from=binary /rust-mcp-filesystem /usr/local/bin/rust-mcp-filesystem

COPY <<'EOF' /app/bridge.py
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

app = FastAPI(title="Filesystem MCP SSE Bridge")
process = None

@app.on_event("startup")
async def startup():
    global process
    process = await asyncio.create_subprocess_exec(
        "rust-mcp-filesystem", "/projects",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"status": "healthy"})

@app.get("/sse")
async def sse_endpoint(request: Request):
    async def event_stream():
        yield "event: endpoint\ndata: /messages\n\n"
        while True:
            if process.stdout.at_eof():
                break
            line = await process.stdout.readline()
            if line:
                yield f"event: message\ndata: {line.decode('utf-8').strip()}\n\n"
                
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/messages")
async def post_message(request: Request):
    body = await request.body()
    process.stdin.write(body + b"\n")
    await process.stdin.drain()
    return {"status": "accepted"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

EXPOSE 8000
CMD ["python", "/app/bridge.py"]