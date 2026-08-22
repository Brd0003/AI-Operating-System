import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

# Target the LiteLLM Gateway
llm = ChatOpenAI(
    model="j.a.r.v.i.s.", 
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.2,
    # Forces LiteLLM to intercept the request and execute brave-search server-side
    extra_body={
        "web_search": True,
        "search_provider": "brave"
    }
)

async def research_node(state: OSState):
    """
    Executes live web search via LiteLLM's Brave Search integration 
    without loading tool schemas into local VRAM.
    """
    sys_msg = SystemMessage(content=(
        "You are the Research Agent. Use live web search results to gather current documentation, "
        "tutorials, or troubleshooting facts. Synthesize the findings into concise context for the Supervisor."
    ))
    
    response = await llm.ainvoke([sys_msg] + state["messages"])
    
    return {
        "messages": [response],
        "current_agent": "research"
    }
