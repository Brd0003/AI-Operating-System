import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

# Standardized environment variables
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.2,
    streaming=True # Enable streaming
)

class PlanOutput(BaseModel):
    plan_steps: list[str] = Field(description="A sequential list of actionable steps to fulfill the user's request.")

async def planner_node(state: OSState):
    sys_msg = SystemMessage(content=(
        "You are the Planning Agent. Break down the user's request into clear, actionable steps. "
        "Do not write code or execute tools. Only provide the plan."
    ))

    planner_llm = llm.with_structured_output(PlanOutput)
    result = await planner_llm.ainvoke([sys_msg] + state["messages"])

    plan_text = "Plan:\n" + "\n".join(f"{i + 1}. {step}" for i, step in enumerate(result.plan_steps))

    return {
        "active_plan": result.plan_steps,
        "current_agent": "planner",
        "messages": [AIMessage(content=plan_text, name="jarvis_planner")],
    }