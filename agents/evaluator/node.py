import os
import sys
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

llm = ChatOpenAI(
    model="j.a.r.v.i.s.", 
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.1
)

class EvaluationResult(BaseModel):
    status: Literal["passed", "failed"] = Field(description="Whether the action succeeded without errors.")
    feedback: str = Field(description="Correction feedback if failed, or confirmation of success.")

async def evaluator_node(state: OSState):
    sys_msg = SystemMessage(content=(
        "You are the QA Evaluator. Review the Executor's action. "
        "If there are errors, mark as 'failed' and explain why. If successful, mark as 'passed'."
    ))
    
    eval_llm = llm.with_structured_output(EvaluationResult)
    result = await eval_llm.ainvoke([sys_msg] + state["messages"])
    
    return {
        "evaluation_feedback": result.status,
        "current_agent": "evaluator",
        "messages": [SystemMessage(content=f"Evaluator Feedback: {result.feedback}")]
    }