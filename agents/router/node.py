import os
import sys
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

# Standardized environment variables
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.1,
    streaming=True # Enable streaming
)

ROUTER_SYS_PROMPT = (
    "You are a semantic traffic cop for the AI-Operating-System. Route the user's request "
    "to exactly one worker:\n"
    "- executor: calls MCP tools directly against the live system. You MUST use the loaded "
    "  MCP tools (such as filesystem tools for listing/reading/writing files in /projects, GitHub, "
    "  and Qdrant). Never suggest manual terminal or bash commands like 'ls -la' because a raw "
    "  bash execution tool is not bound; you must invoke the dedicated MCP tool functions.\n"
    "- planner: breaks a multi-step goal into an ordered plan before anything is executed. If the "
    "  conversation already contains a message starting with 'Plan:', planning is already done — "
    "  route to developer or executor next instead of planner again.\n"
    "- developer: writes or edits code/config content (not a live filesystem action itself).\n"
    "- research: looks things up (web search, docs) rather than acting on the system. If the "
    "  conversation already contains research findings for this query, route to FINISH and "
    "  summarize them instead of researching again.\n"
    "- FINISH: use for pure conversation that needs no system access, or once a prior worker's "
    "  output already answers the request — answer directly in response_to_user.\n"
    "Never claim you lack file or tool access — if the request needs that, route to executor "
    "instead of refusing.\n"
    "If asked what tools, MCP connections, or allowed directories you have, route to EXECUTOR "
    "so it can call the tools live (e.g. list_allowed_directories) and return ground-truth results. "
    "Never answer tool-listing questions from the Supervisor's injected text alone — that list "
    "is a reference, not a substitute for actually calling the tool."
    "Never invent tool names, integrations, or services that are not in the bound tool list."
)

class RouterDecision(BaseModel):
    next_agent: Literal["planner", "developer", "executor", "evaluator", "research", "supervisor", "FINISH"] = Field(
        description="The specialized worker agent to route the task to. Use FINISH if the user request is complete or can be answered directly."
    )
    reasoning: str = Field(description="Why you are routing to this agent based on the user's input.")
    response_to_user: str = Field(
        default="",
        description="Direct reply text to the user. Required and utilized when next_agent is FINISH."
    )

async def router_node(state: OSState):
    sys_msg = SystemMessage(content=ROUTER_SYS_PROMPT)

    router_llm = llm.with_structured_output(RouterDecision)
    result = await router_llm.ainvoke([sys_msg] + state["messages"])

    updates = {
        "current_agent": "router",
        "next_agent": result.next_agent,
        "evaluation_feedback": f"Routed to {result.next_agent}. Reasoning: {result.reasoning}"
    }

    if result.next_agent == "FINISH":
        reply = result.response_to_user or "Task complete."
        updates["messages"] = [AIMessage(content=reply, name="jarvis_router")]

    return updates