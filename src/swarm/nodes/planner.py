from typing import List, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from pydantic import BaseModel, Field
import asyncio
import json

from core.router import ai_router, PLANNER_TIMEOUT
from core.prompts import PLANNER_PROMPT
from core.message_utils import normalize_role

class PlanStep(BaseModel):
    task: str = Field(description="A concrete action to take")
    tool: Optional[str] = Field(default=None, description="Suggested tool name if applicable")

class PlanOutput(BaseModel):
    goal: str = Field(description="Restated goal")
    steps: List[PlanStep] = Field(description="Ordered steps to accomplish the goal")
    success_criteria: str = Field(description="How to know when done")

async def planner_node(state: dict) -> dict:
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content=PLANNER_PROMPT)
    lc_messages = [sys_msg] + [
        {"role": normalize_role(m), "content": m.content}
        for m in messages
    ]
    
    try:
        response = await asyncio.wait_for(
            ai_router.acompletion(
                model="jarvis-local",
                messages=lc_messages,
                temperature=0.1,
                response_format=PlanOutput,
                timeout=PLANNER_TIMEOUT,
            ),
            timeout=PLANNER_TIMEOUT,
        )
        raw_json = response.choices[0].message.content
        try:
            plan = PlanOutput.model_validate_json(raw_json)
            plan_steps = [f"{i+1}. {step.task}" for i, step in enumerate(plan.steps)]
        except Exception:
            # Try to extract JSON
            plan_steps = [raw_json or "Plan unclear"]
    except Exception as e:
        plan_steps = [f"Planning error: {str(e)[:100]}"]

    plan_text = "\n".join(plan_steps) if plan_steps else "No plan generated."
    return {
        "active_plan": plan_steps,
        "current_step": plan_steps[0] if plan_steps else "",
        "messages": [AIMessage(content=f"Plan:\n{plan_text}")],
        "current_agent": "planner",
    }
