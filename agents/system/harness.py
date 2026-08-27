import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from loop import system_agent
from mcp_client import initialize_agent_tools

AGENT_PORT = int(os.environ.get("AGENT_PORT", 10001))
SYSTEM_AGENT_KEY = os.environ.get("SYSTEM_AGENT_KEY")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health", "/docs", "/openapi.json", "/.well-known/agent-card.json"]:
            return await call_next(request)
        
        if request.headers.get("Authorization", "") != f"Bearer {SYSTEM_AGENT_KEY}":
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            
        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Bootstrapping Core System Harness: Dynamic MCP Tools...", flush=True)
    app.state.mcp_tools = await initialize_agent_tools()
    print(f"✅ Loaded {len(app.state.mcp_tools)} native MCP tool(s).", flush=True)
    yield

app = FastAPI(title="J.A.R.V.I.S. Core Harness", lifespan=lifespan)
app.add_middleware(BearerAuthMiddleware)

class SystemAgentExecutor(AgentExecutor):
    """Wires the A2A SDK directly to the LangGraph Swarm."""
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        messages = [{"role": m.role, "content": m.content} for m in context.request.messages]
        
        graph_config = {
            "configurable": {
                "thread_id": context.request.task_id,
                "tools": app.state.mcp_tools,
            },
            "recursion_limit": 50,
        }

        try:
            # Stream directly from the LangGraph nodes
            async for chunk in system_agent.astream({"messages": messages}, config=graph_config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    # Push the Swarm thinking visualizer
                    await event_queue.put(new_agent_text_message(f"\n> *🧠 [Swarm] {node_name.upper()} processing...*\n"))
                    
                    # Push actual LLM output
                    if "messages" in node_output and node_output["messages"]:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content') and isinstance(last_msg.content, str) and last_msg.content:
                            await event_queue.put(new_agent_text_message(last_msg.content))
                            
        except Exception as e:
            await event_queue.put(new_agent_text_message(f"\n**System Error:** {str(e)}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass # Handle LangGraph task cancellation if needed

agent_card = AgentCard(
    name="system-agent",
    description="J.A.R.V.I.S. Core Routing and Evaluation Harness",
    url=os.environ.get("AGENT_URL", f"http://172.70.0.170:{AGENT_PORT}"),
    version="2.2.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text"],
    default_output_modes=["text"],
    skills=[AgentSkill(id="core_ops", name="System Operations", description="Native MCP Routing", tags=["hub"])],
)

request_handler = DefaultRequestHandler(agent_executor=SystemAgentExecutor(), task_store=InMemoryTaskStore())
a2a_app = A2AFastAPIApplication(agent_card=agent_card, http_handler=request_handler)
a2a_app.add_routes_to_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)