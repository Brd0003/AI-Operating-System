import os
import sys
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

# Standardized environment variables
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

# LiteLLM's REST endpoint for searching
SEARCH_ENDPOINT = f"{LITELLM_BASE_URL.rsplit('/v1', 1)[0]}/v1/search/brave-search"

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.2,
    streaming=True # Enable streaming
)

async def _brave_search(query: str, max_results: int = 5) -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                SEARCH_ENDPOINT,
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                json={"query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return f"[Web search unavailable: {e}]"

    results = data.get("results") or data.get("web", {}).get("results") or []
    if not results:
        return "[Web search returned no results]"

    lines = []
    for r in results[:max_results]:
        title = r.get("title", "")
        url = r.get("url", r.get("link", ""))
        snippet = r.get("description", r.get("snippet", ""))
        lines.append(f"- {title} ({url}): {snippet}")
    return "\n".join(lines)

async def research_node(state: OSState):
    user_query = str(state["messages"][-1].content)
    search_results = await _brave_search(user_query)

    sys_msg = SystemMessage(content=(
        "You are the Research Agent. Below are REAL, live web search results for the "
        "user's query. Synthesize your answer strictly from these results. If the results "
        "are empty or unavailable, say so plainly instead of guessing or inventing information.\n\n"
        f"### LIVE SEARCH RESULTS:\n{search_results}"
    ))

    response = await llm.ainvoke([sys_msg] + state["messages"])

    return {
        "messages": [response],
        "current_agent": "research",
    }