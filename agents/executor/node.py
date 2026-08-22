import os
import sys
import asyncio
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

# --- Qdrant Semantic Memory Integration ---
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from agents.system.state import OSState

# Connect to Qdrant (Resolves natively within Docker network)
QDRANT_HOST = os.environ.get("INT_IP_QDRANT", "qdrant")
qdrant = QdrantClient(host=QDRANT_HOST, port=6333)
TOOL_COLLECTION = "qdrant_mcp_tools"

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.1,
    streaming=True,
)

EXECUTOR_SYS_PROMPT = (
    "You are the Executor Agent. Apply the provided configurations or scripts to the system. "
    "Execute dynamic MCP tools securely. Summarize what you executed so the Evaluator can review the outcome."
)

# Root cause of the diagnose.sh 429 burst + "system-agent KeyError: 'data'" crash:
# ensure_tool_index() used to fire one synchronous, unthrottled embedding call
# PER MCP TOOL (GitHub's MCP server alone can expose dozens) with no HTTP error
# handling, against the LITELLM_API_VIRTUAL_KEY_SERVICE_ACCOUNT key, which is
# capped at RPM 20 in LiteLLM. That blew the budget in under a second, LiteLLM
# started returning 429s, and response.json()["data"][0]["embedding"] crashed
# with KeyError on the 429 body (which has no "data" key). Optionally set
# EMBED_INDEX_RPM in .env to tune this against your actual virtual-key budget.
EMBED_INDEX_RPM = int(os.environ.get("EMBED_INDEX_RPM", "15"))
_EMBED_DELAY_SECONDS = 60.0 / max(EMBED_INDEX_RPM, 1)


async def get_embedding(client: httpx.AsyncClient, text: str) -> list[float] | None:
    """Fetch an embedding from the local LiteLLM/Ollama endpoint.
    Never raises — a failed/rate-limited call returns None so one bad
    request can't crash the whole indexing pass or executor turn."""
    url = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1").replace("/v1", "/v1/embeddings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}",
    }
    try:
        response = await client.post(
            url,
            json={"model": "ollama/nomic-embed-text:v1.5", "input": text},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"⚠️ Embedding request failed, skipping: {e}", flush=True)
        return None


async def ensure_tool_index(tools: list):
    """Self-healing: embeds and indexes all MCP tools into Qdrant if the
    collection is missing. Now rate-limited to EMBED_INDEX_RPM and tolerant
    of individual embedding failures instead of crashing the whole pass."""
    if qdrant.collection_exists(TOOL_COLLECTION):
        return

    print(f"⚠️ Collection '{TOOL_COLLECTION}' missing. Indexing {len(tools)} MCP tools to Qdrant...", flush=True)
    qdrant.create_collection(
        collection_name=TOOL_COLLECTION,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE),
    )

    points = []
    async with httpx.AsyncClient() as client:
        for i, tool in enumerate(tools):
            name = getattr(tool, "name", f"tool_{i}")
            desc = getattr(tool, "description", str(tool))
            semantic_text = f"Tool Name: {name}. Description: {desc}"

            vector = await get_embedding(client, semantic_text)
            if vector is not None:
                points.append(PointStruct(id=i, vector=vector, payload={"name": name, "description": desc}))

            if i < len(tools) - 1:
                await asyncio.sleep(_EMBED_DELAY_SECONDS)

    if points:
        qdrant.upsert(collection_name=TOOL_COLLECTION, points=points)
        print(f"✅ Successfully indexed {len(points)}/{len(tools)} tools into Qdrant.", flush=True)
    else:
        print("❌ No tools were successfully embedded — collection left empty; will retry next request.", flush=True)


async def get_semantic_tools(prompt: str, all_tools: list, top_k: int = 5) -> list:
    """Queries Qdrant to retrieve only the specific tools relevant to the user's prompt."""
    if not all_tools:
        return []

    await ensure_tool_index(all_tools)

    async with httpx.AsyncClient() as client:
        prompt_vector = await get_embedding(client, prompt)

    if prompt_vector is None:
        # Embedding the live query failed (e.g. rate-limited) — fail safe by
        # handing the executor the full tool set instead of crashing the turn.
        print("⚠️ Query embedding failed; falling back to full tool set.", flush=True)
        return all_tools

    search_result = qdrant.search(
        collection_name=TOOL_COLLECTION,
        query_vector=prompt_vector,
        limit=top_k,
    )

    retrieved_names = {hit.payload["name"] for hit in search_result}
    filtered_tools = [t for t in all_tools if getattr(t, "name", "") in retrieved_names]

    print(f"🛡️ Qdrant Routing Active: VRAM protected. Supplying {len(filtered_tools)} highly-relevant tools to LLM.", flush=True)
    return filtered_tools


async def executor_node(state: OSState, config: RunnableConfig | None = None):
    config = config or {}
    all_tools = config.get("configurable", {}).get("tools", [])

    user_prompt = str(state["messages"][-1].content)

    safe_tools = await get_semantic_tools(user_prompt, all_tools, top_k=5)

    bound_llm = llm.bind_tools(safe_tools) if safe_tools else llm

    sys_msg = SystemMessage(content=EXECUTOR_SYS_PROMPT)
    response = await bound_llm.ainvoke([sys_msg] + state["messages"])

    return {
        "messages": [response],
        "current_agent": "executor",
        "evaluation_feedback": "pending",
    }


async def tool_runner_node(state: OSState, config: RunnableConfig | None = None):
    """Executes any tool_calls the Executor's LLM just requested against the
    dynamically-loaded MCP tools, and appends the results as ToolMessages so
    the Executor sees them on its next turn."""
    config = config or {}

    tools = config.get("configurable", {}).get("tools", [])
    tools_by_name = {t.name: t for t in tools}

    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", None) or []

    results = []
    for call in tool_calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            results.append(ToolMessage(
                content=f"Error: tool '{call['name']}' not found.",
                tool_call_id=call["id"],
            ))
            continue
        try:
            output = await tool.ainvoke(call["args"])
        except Exception as e:
            output = f"Error executing '{call['name']}': {e}"
        results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))

    return {"messages": results}


def has_pending_tool_calls(state: OSState) -> str:
    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "tool_runner"
    return "evaluator"
