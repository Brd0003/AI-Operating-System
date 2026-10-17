from typing import Literal
from langchain_core.messages import SystemMessage, AIMessage
import asyncio

from core.router import ai_router, RESEARCH_TIMEOUT
from core.prompts import RESEARCH_PROMPT
from core.message_utils import normalize_role

async def research_node(state: dict) -> dict:
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content=RESEARCH_PROMPT)
    lc_messages = [sys_msg] + [
        {"role": normalize_role(m), "content": m.content}
        for m in messages
    ]
    
    try:
        response = await asyncio.wait_for(
            ai_router.acompletion(
                model="jarvis-local",
                messages=lc_messages,
                temperature=0.3,
                timeout=RESEARCH_TIMEOUT,
            ),
            timeout=RESEARCH_TIMEOUT,
        )
        content = response.choices[0].message.content or "No research output."
    except Exception as e:
        content = f"Research error: {str(e)[:100]}"

    return {
        "messages": [AIMessage(content=content)],
        "current_agent": "research",
    }
