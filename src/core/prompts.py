import os

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.md")

with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    SYSTEM_PROMPT: str = _f.read()

# Common prompt constants used across agents
ROUTER_PROMPT = SYSTEM_PROMPT
PLANNER_PROMPT = SYSTEM_PROMPT
DEVELOPER_PROMPT = SYSTEM_PROMPT
EXECUTOR_PROMPT = SYSTEM_PROMPT
RESEARCH_PROMPT = SYSTEM_PROMPT
EVALUATOR_PROMPT = SYSTEM_PROMPT
