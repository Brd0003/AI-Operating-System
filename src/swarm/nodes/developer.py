from typing import Literal
from langchain_core.messages import SystemMessage, AIMessage
import asyncio

from core.router import ai_router, DEVELOPER_TIMEOUT
from core.prompts import DEVELOPER_PROMPT
from core.message_utils import normalize_role

async def developer_node(state: dict) -> dict:
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content=DEVELOPER_PROMPT)
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
                timeout=DEVELOPER_TIMEOUT,
            ),
            timeout=DEVELOPER_TIMEOUT,
        )
        content = response.choices[0].message.content or "No output."
    except Exception as e:
        content = f"Developer error: {str(e)[:100]}"

    return {
        "messages": [AIMessage(content=content)],
        "current_agent": "developer",
    }
