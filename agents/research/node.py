import os
import sys
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

# NOTE: LiteLLM's `search_tools:` block in kernel/litellm/config.yaml exposes a
# SEPARATE REST endpoint, POST /v1/search/<search_tool_name>. It is NOT a
# chat-completions parameter. The old extra_body={"web_search": True,
# "search_provider": "brave"} on the ChatOpenAI client did nothing except get
# forwarded straight through to the underlying Ollama model (drop_params: false
# in config.yaml), which logged "invalid option provided" for both keys and
# silently ignored them — so every "research" turn was ungrounded hallucination.
SEARCH_ENDPOINT = f"{LITELLM_BASE_URL.rsplit('/v1', 1)[0]}/v1/search/brave-search"

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=LITELLM_BASE_URL,
    api_key=LITELLM_MASTER_KEY,
    temperature=0.2,
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

    # LiteLLM's documented response shape for /v1/search isn't fully nailed down
    # here — these fallbacks cover the field-name variants seen across LiteLLM's
    # search provider docs. Run one manual curl against the endpoint after
    # deploying and adjust the key names below if results come back empty.
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
    """
    Runs a real Brave web search via LiteLLM's dedicated /v1/search endpoint,
    then asks the LLM to synthesize strictly from those results.
    """
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
