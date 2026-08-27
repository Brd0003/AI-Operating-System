import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from agents.system.state import OSState

# Standardized environment variables
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.1,
    streaming=True,
)

EXECUTOR_SYS_PROMPT = (
    "You are the J.A.R.V.I.S. Executor Agent. "
    "You have direct access to the system's MCP capabilities. "
    "Your ONLY job is to execute the tools requested by the plan or user. "
    "DO NOT write conversational text. Emit a tool_call immediately. "
    "Once the tool returns a result, summarize the outcome for the Evaluator."
)

async def executor_node(state: OSState, config: RunnableConfig | None = None):
    config = config or {}
    all_tools = config.get("configurable", {}).get("tools", [])

    bound_llm = llm.bind_tools(all_tools) if all_tools else llm

    sys_msg = SystemMessage(content=EXECUTOR_SYS_PROMPT)
    response = await bound_llm.ainvoke([sys_msg] + state["messages"])

    return {
        "messages": [response],
        "current_agent": "executor",
        "evaluation_feedback": "pending",
    }


async def tool_runner_node(state: OSState, config: RunnableConfig | None = None):
    """Executes any tool_calls the Executor's LLM just requested against the
    dynamically-loaded MCP tools, and appends the results as ToolMessages."""
    config = config or {}

    tools = config.get("configurable", {}).get("tools", [])
    tools_by_name = {t.name: t for t in tools}

    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", None) or []

    results = []
    for call in tool_calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            results.append(ToolMessage(
                content=f"Error: tool '{call['name']}' not found.",
                tool_call_id=call["id"],
            ))
            continue
        try:
            output = await tool.ainvoke(call["args"])
        except Exception as e:
            output = f"Error executing '{call['name']}': {e}"
        results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))

    return {"messages": results}

def has_pending_tool_calls(state: OSState) -> str:
    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "tool_runner"
    return "evaluator"