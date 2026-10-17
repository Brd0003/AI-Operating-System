# src/core/message_utils.py
from typing import Any, Dict, Union


def normalize_role(msg: Union[Dict[str, Any], Any]) -> str:
    """
    Normalize LangChain message roles to OpenAI/Ollama compatible roles.
    
    LangChain message types:
    - HumanMessage.type = "human"  -> "user"
    - AIMessage.type = "ai"        -> "assistant"  
    - SystemMessage.type = "system" -> "system"
    - ToolMessage.type = "tool"    -> "tool"
    - FunctionMessage.type = "function" -> "function"
    """
    # Handle dict messages
    if isinstance(msg, dict):
        role = msg.get("role") or msg.get("type") or ""
    else:
        # Handle LangChain message objects
        role = getattr(msg, "role", None) or getattr(msg, "type", "") or ""
    
    role_str = str(role).strip().lower() if role else ""
    
    # Normalize LangChain-specific types
    if role_str == "human":
        return "user"
    if role_str == "ai":
        return "assistant"
    if role_str == "function":
        return "function"
    if role_str == "tool":
        return "tool"
    if role_str == "system":
        return "system"
    if role_str == "developer":
        return "developer"
    if role_str == "thought":
        return "thought"
    
    # Return as-is if already normalized
    return role_str if role_str else "user"


def message_to_openai_dict(msg: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """
    Convert a LangChain message or dict to an OpenAI-compatible message dict.
    Preserves tool_call_id for tool messages.
    """
    # Extract content
    if isinstance(msg, dict):
        content = msg.get("content", "")
    else:
        content = getattr(msg, "content", "")
    
    # Convert content to string for consistency
    if content is None:
        content = ""
    elif not isinstance(content, str):
        content = str(content)
    
    result: Dict[str, Any] = {
        "role": normalize_role(msg),
        "content": content,
    }
    
    # Preserve tool_call_id for tool messages
    if isinstance(msg, dict):
        if msg.get("tool_call_id"):
            result["tool_call_id"] = msg["tool_call_id"]
        if msg.get("name"):
            result["name"] = msg["name"]
        if msg.get("tool_calls"):
            result["tool_calls"] = msg["tool_calls"]
    else:
        if getattr(msg, "tool_call_id", None):
            result["tool_call_id"] = getattr(msg, "tool_call_id")
        if getattr(msg, "name", None):
            result["name"] = getattr(msg, "name")
        if getattr(msg, "tool_calls", None):
            result["tool_calls"] = getattr(msg, "tool_calls")
    
    return result
