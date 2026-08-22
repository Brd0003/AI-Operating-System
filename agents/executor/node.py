import os
import sys
import requests
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

def get_embedding(text: str) -> list[float]:
    """Fetch embedding natively from the local LiteLLM/Ollama endpoint."""
    url = os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1").replace("/v1", "/v1/embeddings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"
    }
    response = requests.post(url, json={"model": "ollama/nomic-embed-text:v1.5", "input": text}, headers=headers)
    return response.json()["data"][0]["embedding"]

def ensure_tool_index(tools: list):
    """Self-healing: Embeds and indexes all MCP tools into Qdrant if the collection is missing."""
    if not qdrant.collection_exists(TOOL_COLLECTION):
        print(f"⚠️ Collection '{TOOL_COLLECTION}' missing. Indexing {len(tools)} MCP tools to Qdrant...", flush=True)
        qdrant.create_collection(
            collection_name=TOOL_COLLECTION,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
        
        points = []
        for i, tool in enumerate(tools):
            name = getattr(tool, 'name', f"tool_{i}")
            desc = getattr(tool, 'description', str(tool))
            
            # Create a rich semantic string to embed
            semantic_text = f"Tool Name: {name}. Description: {desc}"
            vector = get_embedding(semantic_text)
            
            points.append(PointStruct(id=i, vector=vector, payload={"name": name, "description": desc}))
        
        if points:
            qdrant.upsert(collection_name=TOOL_COLLECTION, points=points)
            print(f"✅ Successfully indexed {len(points)} tools into Qdrant.", flush=True)

def get_semantic_tools(prompt: str, all_tools: list, top_k: int = 5) -> list:
    """Queries Qdrant to retrieve only the specific tools relevant to the user's prompt."""
    if not all_tools:
        return []
        
    ensure_tool_index(all_tools)
    
    prompt_vector = get_embedding(prompt)
    search_result = qdrant.search(
        collection_name=TOOL_COLLECTION,
        query_vector=prompt_vector,
        limit=top_k
    )
    
    # Extract the names of the top tools returned by Qdrant
    retrieved_names = {hit.payload["name"] for hit in search_result}
    
    # Filter the actual executable tool objects based on Qdrant's routing
    filtered_tools = [t for t in all_tools if getattr(t, 'name', '') in retrieved_names]
    
    print(f"🛡️ Qdrant Routing Active: VRAM protected. Supplying {len(filtered_tools)} highly-relevant tools to LLM.", flush=True)
    return filtered_tools

async def executor_node(state: OSState, config: RunnableConfig | None = None):
    config = config or {}
    all_tools = config.get("configurable", {}).get("tools", [])

    # Extract the user's latest objective
    user_prompt = str(state["messages"][-1].content)
    
    # Query Qdrant for ONLY the relevant tools
    safe_tools = get_semantic_tools(user_prompt, all_tools, top_k=5)

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
    
    # The runner still has access to ALL tools in memory to execute the action,
    # but the LLM was only burdened with binding the semantic subset.
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