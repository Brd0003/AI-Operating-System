"""
core/router.py — LiteLLM Router wrapping Ollama (primary) + NVIDIA API (fallback).
"""
import os
import json
from typing import Dict, List, Any
from litellm import Router

from core.message_utils import message_to_openai_dict

OLLAMA_API_BASE = os.environ["OLLAMA_API_BASE"]
NVIDIA_API_BASE = os.environ.get("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")

model_list = [
    {
        "model_name": "jarvis-local",
        "litellm_params": {
            "model": "ollama_chat/qwen2.5-coder:7b-instruct",
            "api_base": OLLAMA_API_BASE,
            "num_ctx": 32768,
            "keep_alive": -1,
            "timeout": 120,
            "stream_timeout": 30,
        },
    },
]

fallbacks = []

if NVIDIA_API_KEY:
    model_list.append({
        "model_name": "jarvis-cloud",
        "litellm_params": {
            "model": "openai/meta/llama-3.3-70b-instruct",
            "api_base": NVIDIA_API_BASE,
            "api_key": NVIDIA_API_KEY,
            "timeout": 120,
            "stream_timeout": 30,
        },
    })
    fallbacks.append({"jarvis-local": ["jarvis-cloud"]})

ai_router = Router(
    model_list=model_list,
    fallbacks=fallbacks,
    timeout=120,
    num_retries=1,
    allowed_fails=2,
    cooldown_time=45,
)

ROUTER_TIMEOUT = int(os.environ.get("ROUTER_TIMEOUT", "90"))
PLANNER_TIMEOUT = int(os.environ.get("PLANNER_TIMEOUT", "180"))
DEVELOPER_TIMEOUT = int(os.environ.get("DEVELOPER_TIMEOUT", "300"))
EXECUTOR_TIMEOUT = int(os.environ.get("EXECUTOR_TIMEOUT", "300"))
RESEARCH_TIMEOUT = int(os.environ.get("RESEARCH_TIMEOUT", "180"))
EVALUATOR_TIMEOUT = int(os.environ.get("EVALUATOR_TIMEOUT", "60"))


def format_messages_for_llm(messages: List[Any]) -> List[Dict[str, Any]]:
    formatted = []
    for m in messages:
        try:
            formatted.append(message_to_openai_dict(m))
        except Exception:
            formatted.append({"role": "user", "content": str(m)})
    return formatted


async def classify_messages(messages: List[Any]) -> Dict[str, Any]:
    from core.prompts import ROUTER_PROMPT
    from langchain_core.messages import SystemMessage

    sys_msg = SystemMessage(content=ROUTER_PROMPT + "\n\nRespond in JSON format with keys: next_agent, reasoning, response_to_user")
    formatted = [message_to_openai_dict(sys_msg)] + format_messages_for_llm(messages)

    try:
        response = await ai_router.acompletion(
            model="jarvis-local",
            messages=formatted,
            temperature=0.1,
            timeout=ROUTER_TIMEOUT,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except Exception:
            import re
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            return {"next_agent": "executor", "reasoning": "Classification failed"}
    except Exception as e:
        return {"next_agent": "executor", "reasoning": f"Error: {str(e)}"}
