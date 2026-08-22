import os
import sys
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

# --- Re-enabled the Redis Checkpointer ---
from memory.redis.checkpointer import RedisCheckpointer
from memory.qdrant.explicit import fetch_explicit_memory

from agents.router.node import router_node
from agents.planner.node import planner_node
from agents.developer.node import developer_node
from agents.executor.node import executor_node, tool_runner_node, has_pending_tool_calls
from agents.evaluator.node import evaluator_node
from agents.research.node import research_node

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.2
)

def load_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

async def memory_node(state: OSState, config: RunnableConfig | None = None):
    user_input = str(state["messages"][-1].content)
    try:
        context = await fetch_explicit_memory(user_input)
    except Exception as e:
        print(f"⚠️ Non-fatal memory retrieval skipped: {e}")
        context = "No previous explicit memory context available."
    return {"explicit_memory": context}

async def supervisor_node(state: OSState, config: RunnableConfig | None = None):
    injected_prompt = f"{load_prompt()}\n\n### EXPLICIT MEMORY CONTEXT:\n{state.get('explicit_memory', 'None')}"
    sys_msg = SystemMessage(content=injected_prompt)
    return {"messages": [sys_msg]}

def route_supervisor(state: OSState):
    target = state.get("next_agent", "FINISH")
    if target == "FINISH":
        return END
    return target

def build_system_graph():
    workflow = StateGraph(OSState)

    workflow.add_node("memory", memory_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("developer", developer_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("tool_runner", tool_runner_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("research", research_node)

    workflow.set_entry_point("memory")
    workflow.add_edge("memory", "supervisor")
    workflow.add_edge("supervisor", "router")
    workflow.add_conditional_edges("router", route_supervisor)
    workflow.add_edge("planner", "router")
    workflow.add_edge("developer", "router")
    workflow.add_edge("research", "router")
    workflow.add_conditional_edges(
        "executor", has_pending_tool_calls, {"tool_runner": "tool_runner", "evaluator": "evaluator"}
    )
    workflow.add_edge("tool_runner", "executor")
    workflow.add_edge("evaluator", "router")

    # --- Redis Memory Restored ---
    memory_saver = RedisCheckpointer()
    return workflow.compile(checkpointer=memory_saver)

system_agent = build_system_graph()