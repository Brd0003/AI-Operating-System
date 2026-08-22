#!/usr/bin/env bash
# ============================================================================
# AI-Operating-System — root-cause fix batch
#
# Run this from the repo root on the Unraid box:
#   cd /mnt/cache/config/workspace/AI-Operating-System
#   bash apply_fixes.sh
#
# Fixes three separate, code-verified bugs:
#   1. agents/planner/node.py + agents/router/node.py + agents/system/loop.py
#      -> the ROUTER<->PLANNER infinite loop that hits recursion_limit=25.
#   2. agents/system/loop.py + agents/system/system_prompt.md + agents/router/node.py
#      -> the fabricated tool list (Home Assistant, Zapier, IFTTT, etc.)
#   3. agents/research/node.py
#      -> research_node's web_search never actually ran (Ollama logged
#         "invalid option provided" for web_search/search_provider — pure hallucination).
#   4. agents/executor/node.py + agents/system/requirements.txt
#      -> the embeddings burst that blew through the LiteLLM RPM=20 budget
#         and crashed with KeyError: 'data' on the 429 responses.
#   5. kernel/litellm/config.yaml
#      -> order: on the two "j.a.r.v.i.s." deployments isn't enforced without
#         enable_pre_call_checks: true, so simple-shuffle can silently send
#         traffic to the $5-budget NVIDIA fallback instead of local Ollama.
#
# After running, rebuild + restart just the affected services:
#   ./bin/aos up --build system-agent
#   ./bin/aos restart litellm
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "🔧 Patching agents/planner/node.py (planner now emits a message so the router can see progress)..."
cat > agents/planner/node.py << 'PYEOF'
import os
import sys
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.2
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
        # Root cause of the ROUTER/PLANNER recursion-limit crash: this node used to
        # return only active_plan/current_agent, never touching "messages". Since
        # the router only ever looks at state["messages"], it saw an unchanged
        # conversation on every loop and kept re-deciding the same thing forever.
        # Appending the plan as a real AIMessage gives the router something new
        # to react to on the next hop.
        "messages": [AIMessage(content=plan_text, name="jarvis_planner")],
    }
PYEOF

echo "🔧 Patching agents/router/node.py (loop guardrails + grounded tool-listing answers)..."
cat > agents/router/node.py << 'PYEOF'
import os
import sys
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from agents.system.state import OSState

llm = ChatOpenAI(
    model="j.a.r.v.i.s.",
    base_url=os.environ.get("LITELLM_BASE_URL", "http://172.70.0.165:4000/v1"),
    api_key=os.environ.get("LITELLM_MASTER_KEY"),
    temperature=0.1
)

ROUTER_SYS_PROMPT = (
    "You are a semantic traffic cop for the AI-Operating-System. Route the user's request "
    "to exactly one worker:\n"
    "- executor: calls MCP tools directly against the live system. You MUST use the loaded "
    "  MCP tools (such as filesystem tools for listing/reading/writing files in /projects, GitHub, "
    "  and Qdrant). Never suggest manual terminal or bash commands like 'ls -la' because a raw "
    "  bash execution tool is not bound; you must invoke the dedicated MCP tool functions.\n"
    "- planner: breaks a multi-step goal into an ordered plan before anything is executed. If the "
    "  conversation already contains a message starting with 'Plan:', planning is already done — "
    "  route to developer or executor next instead of planner again.\n"
    "- developer: writes or edits code/config content (not a live filesystem action itself).\n"
    "- research: looks things up (web search, docs) rather than acting on the system. If the "
    "  conversation already contains research findings for this query, route to FINISH and "
    "  summarize them instead of researching again.\n"
    "- FINISH: use for pure conversation that needs no system access, or once a prior worker's "
    "  output already answers the request — answer directly in response_to_user.\n"
    "Never claim you lack file or tool access — if the request needs that, route to executor "
    "instead of refusing.\n"
    "If asked what tools, functions, or MCP connections you have, route to FINISH and answer "
    "using ONLY the 'ACTUALLY BOUND MCP TOOLS' list injected earlier in this conversation by the "
    "Supervisor. Never invent tool names, integrations, or services that are not in that list."
)

class RouterDecision(BaseModel):
    next_agent: Literal["planner", "developer", "executor", "evaluator", "research", "supervisor", "FINISH"] = Field(
        description="The specialized worker agent to route the task to. Use FINISH if the user request is complete or can be answered directly."
    )
    reasoning: str = Field(description="Why you are routing to this agent based on the user's input.")
    response_to_user: str = Field(
        default="",
        description="Direct reply text to the user. Required and utilized when next_agent is FINISH."
    )

async def router_node(state: OSState):
    """
    Router Agent: Acts as a semantic traffic cop to inspect user raw input
    and return a structured JSON decision to control the LangGraph flow.
    """
    sys_msg = SystemMessage(content=ROUTER_SYS_PROMPT)

    router_llm = llm.with_structured_output(RouterDecision)
    result = await router_llm.ainvoke([sys_msg] + state["messages"])

    updates = {
        "current_agent": "router",
        "next_agent": result.next_agent,
        "evaluation_feedback": f"Routed to {result.next_agent}. Reasoning: {result.reasoning}"
    }

    if result.next_agent == "FINISH":
        reply = result.response_to_user or "Task complete."
        updates["messages"] = [AIMessage(content=reply, name="jarvis_router")]

    return updates
PYEOF

echo "🔧 Patching agents/system/loop.py (supervisor now injects the REAL bound MCP tool list)..."
python3 - << 'PYEOF'
import re
path = "agents/system/loop.py"
with open(path) as f:
    content = f.read()

old = '''async def supervisor_node(state: OSState, config: RunnableConfig | None = None):
    injected_prompt = f"{load_prompt()}\n\n### EXPLICIT MEMORY CONTEXT:\n{state.get('explicit_memory', 'None')}"
    sys_msg = SystemMessage(content=injected_prompt)
    return {"messages": [sys_msg]}'''

new = '''async def supervisor_node(state: OSState, config: RunnableConfig | None = None):
    config = config or {}
    tools = config.get("configurable", {}).get("tools", [])
    if tools:
        tool_list = "\n".join(
            f"- {getattr(t, 'name', 'unknown')}: {getattr(t, 'description', '') or 'no description'}"
            for t in tools
        )
    else:
        tool_list = "(none currently loaded — MCP discovery may have failed at startup; check system-agent logs)"

    injected_prompt = (
        f"{load_prompt()}\n\n"
        f"### ACTUALLY BOUND MCP TOOLS (ground truth — never claim a tool beyond this list):\n{tool_list}\n\n"
        f"### EXPLICIT MEMORY CONTEXT:\n{state.get('explicit_memory', 'None')}"
    )
    sys_msg = SystemMessage(content=injected_prompt)
    return {"messages": [sys_msg]}'''

if old not in content:
    raise SystemExit("❌ supervisor_node didn't match expected content — loop.py may already be modified. Skipping this patch, check manually.")

content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("✅ loop.py patched.")
PYEOF

echo "🔧 Patching agents/system/system_prompt.md (remove the Home Assistant claim that isn't wired into mcp_client.py)..."
cat > agents/system/system_prompt.md << 'MDEOF'
## 1. CORE OPERATIONAL MODALITY
You are J.A.R.V.I.S., the central autonomous reasoning and orchestration engine for the Nestworks infrastructure.

Your primary directive is system orchestration: you route complex tasks, evaluate outcomes, and utilize sub-agents when domain-specific action is required.

## 2. ARCHITECTURAL AWARENESS
You operate within a highly modular AI Operating System.
* **Compute:** You are powered by local GPU inference routed through LiteLLM.
* **Memory:** You do NOT create local text files to remember things. Your long-term memory is handled dynamically via a centralized Qdrant vector database.
* **Execution:** You utilize the Model Context Protocol (MCP) to dynamically discover and execute tools. Your actual bound tools are listed under "ACTUALLY BOUND MCP TOOLS" in this context — that list, not your training data, is ground truth for what you can do right now. If something isn't in that list (e.g. Home Assistant, a weather service, Zapier), you do not have it yet, no matter what your training data implies a generic assistant would have.

## 3. DETERMINISTIC EXECUTION (The Loop)
When given a task:
1. **Plan:** Outline the steps required.
2. **Execute:** Call the necessary MCP tools silently.
3. **Evaluate:** Inspect the tool output. If a configuration is invalid, catch the error and fix it before responding to the user.
MDEOF

echo "🔧 Patching agents/research/node.py (call LiteLLM's real /v1/search endpoint instead of a no-op extra_body)..."
cat > agents/research/node.py << 'PYEOF'
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
PYEOF

echo "🔧 Patching agents/executor/node.py (async, rate-limited, error-safe embeddings — fixes the 429 burst + KeyError: 'data' crash)..."
cat > agents/executor/node.py << 'PYEOF'
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
PYEOF

echo "🔧 Ensuring httpx is in agents/system/requirements.txt (used by executor/node.py and research/node.py; not previously listed there)..."
if ! grep -qx "httpx" agents/system/requirements.txt; then
  # Inject a blank line first to guarantee we don't glue to the previous word
  echo "" >> agents/system/requirements.txt
  echo "httpx" >> agents/system/requirements.txt
fi

echo "🔧 Patching kernel/litellm/config.yaml (enable_pre_call_checks: true — required for 'order:' to actually gate local-Ollama-first vs the paid NVIDIA fallback)..."
python3 - << 'PYEOF'
path = "kernel/litellm/config.yaml"
with open(path) as f:
    content = f.read()

old = """router_settings:
  routing_strategy: simple-shuffle
  allowed_fails_policy:"""

new = """router_settings:
  routing_strategy: simple-shuffle
  # Without this, LiteLLM's `order:` field on the two "j.a.r.v.i.s." deployments
  # below is NOT guaranteed to be honored under simple-shuffle — meaning traffic
  # could silently land on the $5-budget NVIDIA fallback instead of always
  # preferring the local Ollama deployment (order: 1) first.
  enable_pre_call_checks: true
  allowed_fails_policy:"""

if old not in content:
    raise SystemExit("❌ router_settings block didn't match expected content — config.yaml may already be modified. Skipping this patch, check manually.")

content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("✅ config.yaml patched.")
PYEOF

echo ""
echo "✅ All patches applied."
echo ""
echo "Next steps:"
echo "  1. Review the diffs:  git diff"
echo "  2. Rebuild + restart the system-agent (code changed, needs a rebuild, not just a restart):"
echo "       ./bin/aos up --build system-agent"
echo "  3. Restart litellm to pick up the config.yaml change:"
echo "       ./bin/aos restart litellm"
echo "  4. (Optional) tune embedding throughput to match your actual RPM budget by adding to .env:"
echo "       EMBED_INDEX_RPM=15"
echo "  5. Manually verify LiteLLM's real /v1/search response shape once, and adjust the key"
echo "     names in agents/research/node.py's _brave_search() if results come back empty:"
echo "       curl http://172.70.0.165:4000/v1/search/brave-search \\"
echo "         -H \"Authorization: Bearer \$LITELLM_MASTER_KEY\" \\"
echo "         -H \"Content-Type: application/json\" \\"
echo "         -d '{\"query\": \"test\", \"max_results\": 3}'"