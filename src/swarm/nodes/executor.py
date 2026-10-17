from typing import Literal, List, Dict, Any
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
import asyncio
import json

from core.router import ai_router, EXECUTOR_TIMEOUT
from core.prompts import EXECUTOR_PROMPT
from core.mcp_tools import get_tools
from core.ha_tools import (
    turn_on_light,
    turn_off_light,
    set_light_brightness,
    toggle_light,
    get_entity_state,
    call_service,
    list_entities,
    scene_activate,
    media_play,
    media_pause,
    climate_set_temperature,
    cover_open,
    cover_close,
)
from core.n8n_tool import trigger_n8n_workflow
from core.message_utils import normalize_role, message_to_openai_dict

# Build base static tools
def _get_base_tools() -> List[BaseTool]:
    return [
        turn_on_light,
        turn_off_light,
        set_light_brightness,
        toggle_light,
        get_entity_state,
        call_service,
        list_entities,
        scene_activate,
        media_play,
        media_pause,
        climate_set_temperature,
        cover_open,
        cover_close,
        trigger_n8n_workflow,
    ]

SYSTEM_INSTRUCTIONS = (
    EXECUTOR_PROMPT
    + "\n\nYou have access to tools. When you need to call a tool, respond with a tool_call. "
    + "After receiving tool results, continue until the task is complete."
)

async def executor_node(state: dict) -> dict:
    messages: List[Any] = list(state.get("messages", []))
    max_iterations = 10
    iterations = 0

    # Dynamically fetch tools with proper await
    tools = _get_base_tools()
    try:
        mcp = await get_tools()
        if mcp:
            tools.extend(mcp)
    except Exception:
        pass
    
    tool_map = {t.name: t for t in tools}

    while iterations < max_iterations:
        iterations += 1
        sys_msg = SystemMessage(content=SYSTEM_INSTRUCTIONS)
        lc_messages = [sys_msg] + [
            message_to_openai_dict(m)
            for m in messages
        ]
        
        try:
            response = await asyncio.wait_for(
                ai_router.acompletion(
                    model="jarvis-local",
                    messages=lc_messages,
                    tools=[{"type": "function", "function": t.args_schema.model_json_schema() if hasattr(t.args_schema, "model_json_schema") else {}} for t in tools],
                    tool_choice="auto",
                    temperature=0.1,
                    timeout=EXECUTOR_TIMEOUT,
                ),
                timeout=EXECUTOR_TIMEOUT,
            )
            msg = response.choices[0].message
        except Exception as e:
            return {
                "messages": [AIMessage(content=f"Executor error: {str(e)[:100]}")],
                "current_agent": "executor",
                "evaluation_feedback": "failed",
            }

        tool_calls = getattr(msg, "tool_calls", None) or (msg.get("tool_calls") if isinstance(msg, dict) else [])
        if tool_calls:
            assistant_msg = AIMessage(
                content=msg.content or "",
                tool_calls=[
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "args": json.loads(tc.function.arguments) if hasattr(tc.function, "arguments") else {},
                    }
                    for tc in tool_calls
                ],
            )
            messages.append(assistant_msg)
            
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if hasattr(tc.function, "arguments") else {}
                except Exception:
                    args = {}
                tool = tool_map.get(tool_name)
                if tool is None:
                    result_str = f"Tool not found: {tool_name}"
                else:
                    try:
                        if asyncio.iscoroutinefunction(tool.invoke):
                            result = await tool.ainvoke(args)
                        else:
                            result = tool.invoke(args)
                        result_str = str(result) if result is not None else "OK"
                    except Exception as e:
                        result_str = f"Tool error: {str(e)[:200]}"
                
                messages.append(
                    ToolMessage(
                        content=result_str,
                        tool_call_id=tc.id,
                        name=tool_name,
                    )
                )
            continue
        else:
            final_content = msg.content or "Done."
            return {
                "messages": [AIMessage(content=final_content)],
                "current_agent": "executor",
                "evaluation_feedback": "passed",
            }

    return {
        "messages": [AIMessage(content="Executor reached iteration limit.")],
        "current_agent": "executor",
        "evaluation_feedback": "passed",
    }