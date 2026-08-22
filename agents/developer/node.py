import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

llm = ChatOpenAI(
    model="j.a.r.v.i.s.", 
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.2
)

async def developer_node(state: OSState):
    sys_msg = SystemMessage(content=(
        "You are the Developer Agent. Your job is to write perfectly formatted code, YAML, or Bash scripts. "
        "Adhere strictly to the requested plan. Provide the code blocks clearly."
    ))
    
    response = await llm.ainvoke([sys_msg] + state["messages"])
    
    return {
        "messages": [response],
        "current_agent": "developer"
    }
