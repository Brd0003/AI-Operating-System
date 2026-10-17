import os
import json
import time
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Part, TextPart, TaskState
from a2a.utils import new_agent_text_message

from swarm.graph import system_agent

# Use environment variable strings directly
AGENT_PORT = int(os.environ.get("AGENT_PORT", 10001))
SYSTEM_AGENT_KEY = os.environ.get("SYSTEM_AGENT_KEY", "")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Whitelisted endpoints that bypass auth
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json", "/.well-known/agent-card.json", "/v1/models"]:
            return await call_next(request)
            
        auth_header = request.headers.get("Authorization", "")
        x_api_key = request.headers.get("x-api-key", "")
        
        if auth_header != f"Bearer {SYSTEM_AGENT_KEY}" and x_api_key != SYSTEM_AGENT_KEY:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            
        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("J.A.R.V.I.S. Core Harness ready.", flush=True)
    yield

app = FastAPI(title="J.A.R.V.I.S. Core Harness", lifespan=lifespan)
app.add_middleware(BearerAuthMiddleware)

def _graph_config(thread_id: str) -> dict:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 25,
    }

def get_message_content(msg) -> str:
    if hasattr(msg, "content"):
        return str(msg.content)
    if isinstance(msg, dict):
        return str(msg.get("content", ""))
    return str(msg)

def _parse_anthropic_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(item["text"])
        return "\n".join(parts)
    return str(content)

class SystemAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()
        user_text = context.get_user_input()

        try:
            result = await system_agent.ainvoke(
                {"messages": [{"role": "user", "content": user_text}]},
                config=_graph_config(context.context_id),
            )
            messages = result.get("messages", [])
            if messages:
                content = get_message_content(messages[-1])
                await updater.add_artifact([Part(root=TextPart(text=content))], append=True)
            await updater.complete()
        except Exception as e:
            await updater.failed(message=new_agent_text_message(
                f"\n**System Error:** {str(e)}", context.context_id, context.task_id
            ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

async def _run_graph_and_respond(messages, model, stream, thread_id):
    lc_messages = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
    ]

    if not stream:
        try:
            result = await system_agent.ainvoke(
                {"messages": lc_messages},
                config=_graph_config(thread_id),
            )
            msgs = result.get("messages", [])
            last_msg = msgs[-1] if msgs else None
            full_content = get_message_content(last_msg) if last_msg else "Processing complete."
        except Exception as e:
            full_content = f"**System Error:** {e}"

        return JSONResponse({
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": full_content},
                "finish_reason": "stop",
            }],
        })

    async def stream_generator():
        chat_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())

        def chunk(text: str, finish_reason=None):
            return json.dumps({
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": text},
                    "finish_reason": finish_reason,
                }],
            })

        try:
            result = await system_agent.ainvoke(
                {"messages": lc_messages},
                config=_graph_config(thread_id),
            )
            msgs = result.get("messages", [])
            if msgs:
                content = get_message_content(msgs[-1])
                if content.strip():
                    yield f"data: {chunk(content)}\n\n"

            yield f"data: {chunk('', finish_reason='stop')}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {chunk(f'**System Error:** {e}', finish_reason='error')}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

async def _run_anthropic_graph_and_respond(lc_messages, model, stream, thread_id):
    if not stream:
        try:
            result = await system_agent.ainvoke(
                {"messages": lc_messages},
                config=_graph_config(thread_id),
            )
            msgs = result.get("messages", [])
            last_msg = msgs[-1] if msgs else None
            full_content = get_message_content(last_msg) if last_msg else "Processing complete."
        except Exception as e:
            full_content = f"**System Error:** {e}"

        return JSONResponse({
            "id": f"msg_{uuid.uuid4().hex}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": full_content
                }
            ],
            "model": model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}
        })

    async def stream_generator():
        msg_id = f"msg_{uuid.uuid4().hex}"
        
        # message_start
        yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'content': [], 'model': model, 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
        
        # content_block_start
        yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"

        def chunk(text: str):
            return f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}})}\n\n"

        try:
            result = await system_agent.ainvoke(
                {"messages": lc_messages},
                config=_graph_config(thread_id),
            )
            msgs = result.get("messages", [])
            if msgs:
                content = get_message_content(msgs[-1])
                if content.strip():
                    yield chunk(content)
        except Exception as e:
            yield chunk(f"**System Error:** {e}")

        # content_block_stop
        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"

        # message_delta
        yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 0}})}\n\n"

        # message_stop
        yield "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

async def _handle_openai_request(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    messages = body.get("messages", [])
    model = body.get("model", "system-agent")
    stream = body.get("stream", False)

    # Honour caller-supplied thread ID (e.g. from Home Assistant Assist) so
    # QdrantCheckpointer maintains per-session memory across turns.
    thread_id = request.headers.get("X-Thread-ID") or str(uuid.uuid4())

    return await _run_graph_and_respond(messages, model, stream, thread_id)

@app.post("/chat/completions")
async def openai_chat_completions(request: Request):
    return await _handle_openai_request(request)

@app.post("/v1/chat/completions")
async def openai_v1_chat_completions(request: Request):
    return await _handle_openai_request(request)

@app.post("/v1/messages")
async def anthropic_messages_translation(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    lc_messages = []
    
    # Extract top-level system prompt
    system_prompt = body.get("system")
    if system_prompt:
        system_text = _parse_anthropic_content(system_prompt)
        if system_text.strip():
            lc_messages.append({"role": "system", "content": system_text})
            
    # Extract standard messages
    for m in body.get("messages", []):
        role = m.get("role", "user")
        content = _parse_anthropic_content(m.get("content", ""))
        lc_messages.append({"role": role, "content": content})

    model = body.get("model", "system-agent")
    stream = body.get("stream", False)

    thread_id = request.headers.get("X-Thread-ID") or request.headers.get("x-thread-id") or str(uuid.uuid4())

    return await _run_anthropic_graph_and_respond(lc_messages, model, stream, thread_id)

@app.get("/v1/models")
async def list_models():
    return JSONResponse({
        "object": "list",
        "data": [{
            "id": "system-agent",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "jarvis",
        }],
    })

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return StreamingResponse(
        iter(["# HELP aos_system_agent_up Status of agent\n# TYPE aos_system_agent_up gauge\naos_system_agent_up 1\n"]), 
        media_type="text/plain"
    )

agent_card = AgentCard(
    name="system-agent",
    description="J.A.R.V.I.S. — Nestworks AI Operating System Core",
    url=os.environ["AGENT_URL"],
    version="3.0.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text"],
    default_output_modes=["text"],
    skills=[AgentSkill(
        id="core_ops",
        name="System Operations",
        description="Reasoning and orchestration",
        tags=["hub"],
    )],
)

request_handler = DefaultRequestHandler(
    agent_executor=SystemAgentExecutor(),
    task_store=InMemoryTaskStore(),
)
a2a_app = A2AFastAPIApplication(agent_card=agent_card, http_handler=request_handler)
a2a_app.add_routes_to_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)