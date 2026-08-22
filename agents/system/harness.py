import os
import uvicorn
import time
import uuid
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from langgraph.errors import GraphRecursionError

# --- NEW IMPORT REQUIRED FOR THE FILTER ---
from langchain_core.messages import AIMessage

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message, new_task

from loop import system_agent
from mcp_client import initialize_agent_tools

AGENT_PORT = int(os.environ.get("AGENT_PORT", 10001))
SYSTEM_AGENT_KEY = os.environ.get("SYSTEM_AGENT_KEY")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in [
            "/health",
            "/docs",
            "/openapi.json",
            "/.well-known/agent-card.json",
        ]:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not SYSTEM_AGENT_KEY:
            return JSONResponse(status_code=500, content={"detail": "Server security misconfigured: SYSTEM_AGENT_KEY not set."})

        expected_token = f"Bearer {SYSTEM_AGENT_KEY}"
        if auth_header != expected_token:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: Invalid token."})

        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        "Bootstrapping Core System Harness: Dynamic MCP Tools...",
        flush=True,
    )

    app.state.mcp_tools = await initialize_agent_tools()

    print(
        f"✅ Loaded {len(app.state.mcp_tools)} dynamic MCP tool(s) into system memory.",
        flush=True,
    )

    yield

    print("Shutting down System Harness...", flush=True)

app = FastAPI(title="System Agent Harness", lifespan=lifespan)
app.add_middleware(BearerAuthMiddleware)

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def openai_chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    thread_id = str(uuid.uuid4())
    graph_config = {
        "configurable": {
            "thread_id": thread_id,
            "tools": request.app.state.mcp_tools,
        },
        "recursion_limit": 25,
    }

    chat_id = f"chatcmpl-{uuid.uuid4().hex}"

    async def stream_generator():
        try:
            async for chunk in system_agent.astream(
                {"messages": messages}, 
                config=graph_config, 
                stream_mode="updates"
            ):
                for node_name, node_output in chunk.items():
                    marker = {
                        "id": chat_id, "object": "chat.completion.chunk", "created": int(time.time()), 
                        "model": "system-agent", 
                        "choices": [{"index": 0, "delta": {"content": f"\n\n> *🧠 [Swarm] {node_name.upper()} processing...*\n\n"}}]}
                    yield f"data: {json.dumps(marker)}\n\n"
                    
                    if "messages" in node_output and node_output["messages"]:
                        last_msg = node_output["messages"][-1]
                        
                        # --- THE FIX THAT PREVENTS THE PROMPT LEAK ---
                        # Only push text to the UI if it is an actual AI-generated answer.
                        if isinstance(last_msg, AIMessage) and isinstance(last_msg.content, str) and last_msg.content:
                            data = {
                                "id": chat_id, "object": "chat.completion.chunk", "created": int(time.time()), 
                                "model": "system-agent", 
                                "choices": [{"index": 0, "delta": {"content": last_msg.content}}]}
                            yield f"data: {json.dumps(data)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_chunk = {
                "id": chat_id, "object": "chat.completion.chunk", "created": int(time.time()), 
                "model": "system-agent", 
                "choices": [{"index": 0, "delta": {"content": f"\n\n**System Error:** {str(e)}"}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"

    if stream:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        final_text = "Task completed."
        current_state = await system_agent.ainvoke({"messages": messages}, config=graph_config)
        if "messages" in current_state and current_state["messages"]:
            final_text = current_state["messages"][-1].content
        return JSONResponse({
            "id": chat_id, "object": "chat.completion", "created": int(time.time()), "model": "system-agent",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": final_text}, "finish_reason": "stop"}]
        })

class SystemAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass 
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

agent_card = AgentCard(
    name="system-agent",
    description="J.A.R.V.I.S. Core Routing and Evaluation Harness with Dynamic MCP",
    url=os.environ.get("AGENT_URL", f"http://172.70.0.170:{AGENT_PORT}"),
    version="2.1.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text"],
    default_output_modes=["text"],
    security_schemes={"BearerAuth": {"type": "http", "scheme": "bearer"}},
    security=[{"BearerAuth": []}],
    skills=[AgentSkill(id="core_ops", name="System Operations", description="Dynamic MCP Routing", tags=["hub"])],
)

request_handler = DefaultRequestHandler(agent_executor=SystemAgentExecutor(), task_store=InMemoryTaskStore())
a2a_app = A2AFastAPIApplication(agent_card=agent_card, http_handler=request_handler)
a2a_app.add_routes_to_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)