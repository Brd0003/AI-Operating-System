import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

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
    streaming=True # Enable streaming for consistency
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