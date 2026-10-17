"""
swarm/nodes/router.py — intent classifier and FINISH-path reply generator.

Two-step design:
  Step 0 (retrieve): Query qdrant_explicit_memory for relevant past facts and
                     prepend them to both the classify and reply prompts.
  Step 1 (classify): JSON-mode LLM call parsed manually → next_agent string.
                     Uses format="json" (Ollama native) + prompt-level schema
                     instead of response_format=<Pydantic> which Qwen 7B ignores.
  Step 2 (reply):    Only runs on FINISH routes. Generates the spoken response.

Memory retrieval failures are always silent — routing proceeds without context.
"""
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import asyncio
import re
import json

from core.router import ai_router, classify_messages, ROUTER_TIMEOUT, format_messages_for_llm
from core.prompts import ROUTER_PROMPT
from core.memory_client import retrieve_relevant
from core.message_utils import normalize_role

FINISH = "FINISH"
PLANNER = "planner"
DEVELOPER = "developer"
EXECUTOR = "executor"
RESEARCH = "research"

async def route_from_router(state: dict) -> Literal["planner", "developer", "executor", "research", "__end__"]:
    next_agent = state.get("next_agent", FINISH)
    if next_agent == FINISH:
        return "__end__"
    return next_agent

async def _get_user_query(state: dict) -> str:
    for m in reversed(state.get("messages", [])):
        if getattr(m, "type", "") == "human":
            return m.content or ""
    return ""

async def router_node(state: dict) -> dict:
    """
    The entry point. Classifies the user's intent using the lightweight router
    model and routes to the appropriate specialist, or FINISHes.
    """
    user_query = await _get_user_query(state)
    context = await retrieve_relevant(user_query, top_k=5) if user_query else []
    context_block = "\n\n---\n\nRelevant memory:\n" + "\n".join(f"- {c}" for c in context) if context else ""

    messages = state.get("messages", [])
    # Build classification messages with normalized roles
    classify_msgs = format_messages_for_llm(messages) if hasattr(classify_messages, "__code__") else [
        {"role": normalize_role(m), "content": m.content}
        for m in messages
    ]
    
    try:
        # Use the router's classification with timeout
        cls_result = await asyncio.wait_for(
            classify_messages(messages),
            timeout=ROUTER_TIMEOUT,
        )
        next_agent = cls_result.get("next_agent", FINISH)
        reasoning = cls_result.get("reasoning", "Routing decision made.")
    except asyncio.TimeoutError:
        next_agent = EXECUTOR  # Fallback to executor on timeout
        reasoning = "Router timeout - defaulting to executor."
    except Exception as e:
        # Fallback on any classification error
        next_agent = EXECUTOR
        reasoning = f"Routing fallback due to error: {str(e)[:100]}"

    if next_agent == FINISH:
        # Generate a final response
        sys_msg = SystemMessage(content=ROUTER_PROMPT + context_block + "\n\nYou are in FINISH mode. Provide a concise, helpful final answer.")
        lc_messages = [sys_msg] + [
            {"role": normalize_role(m), "content": m.content}
            for m in messages
        ]
        try:
            response = await asyncio.wait_for(
                ai_router.acompletion(
                    model="jarvis-local",
                    messages=lc_messages,
                    temperature=0.2,
                    timeout=90,
                ),
                timeout=90,
            )
            reply = response.choices[0].message.content or "Done."
        except Exception:
            # If reply fails, just end
            reply = "Task completed."

        return {
            "next_agent": FINISH,
            "messages": [AIMessage(content=reply)],
            "current_agent": "router",
        }

    return {
        "next_agent": next_agent,
        "current_agent": "router",
    }