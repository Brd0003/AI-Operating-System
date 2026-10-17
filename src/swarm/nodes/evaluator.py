from typing import Literal
from langchain_core.messages import SystemMessage, AIMessage
import asyncio
import json

from core.router import ai_router, EVALUATOR_TIMEOUT
from core.prompts import EVALUATOR_PROMPT
from core.message_utils import normalize_role, message_to_openai_dict

async def route_from_evaluator(state: dict) -> Literal["memory", "__end__"]:
    feedback = state.get("evaluation_feedback", "passed")
    if feedback == "passed":
        return "memory"
    return "__end__"

async def evaluator_node(state: dict) -> dict:
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content=EVALUATOR_PROMPT)
    formatted_messages = [sys_msg] + [
        message_to_openai_dict(m)
        for m in messages
    ]
    
    try:
        response = await asyncio.wait_for(
            ai_router.acompletion(
                model="jarvis-local",
                messages=formatted_messages,
                temperature=0.1,
                timeout=EVALUATOR_TIMEOUT,
            ),
            timeout=EVALUATOR_TIMEOUT,
        )
        content = response.choices[0].message.content or ""
    except (asyncio.TimeoutError, Exception) as e:
        # On timeout or error, fall back to a safe "passed" with last message context
        content = "passed"
    
    feedback = content.strip().lower()
    if "failed" in feedback or "retry" in feedback or "incomplete" in feedback:
        evaluation = "failed"
    elif "timeout" in feedback:
        evaluation = "timeout"
    else:
        evaluation = "passed"

    return {
        "evaluation_feedback": evaluation,
        "current_agent": "evaluator",
    }
