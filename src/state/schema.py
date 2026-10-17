from typing import Annotated, TypedDict, List, Dict, Any, NotRequired
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class OSState(TypedDict):
    # The active conversation and tool call history
    messages: Annotated[List[BaseMessage], add_messages]

    # Multi-Agent Routing State
    current_agent: str
    next_agent: str

    # Task Execution & Evaluation
    active_plan: List[str]
    current_step: str
    evaluation_feedback: str
    is_task_complete: bool

    # Telemetry & Safety Limits
    trace_id: str
    recursion_count: NotRequired[int]