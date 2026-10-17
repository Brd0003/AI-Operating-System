"""
swarm/nodes/memory.py — semantic memory extraction node.

Placement in graph: evaluator → memory_node → END  (only on evaluation_feedback == "passed")

Responsibility:
  1. Condense the completed conversation into 3–5 declarative fact strings
     using a single, low-temperature LLM call (no tool use).
  2. Upsert those facts into the qdrant_explicit_memory collection via the
     core.memory_client module (direct qdrant-client, not MCP).

Design choices:
  - Uses a tiny max_tokens budget (256) — this is a summarization pass, not a
    chat turn. Keeping it small prevents Qwen 7B from hallucinating extra prose.
  - Parses the LLM output as a newline-separated list. If the model returns
    numbered lines ("1. ...", "- ..."), they are stripped to bare facts.
  - On any error (LLM timeout, Qdrant write failure, parse failure), the node
    logs and returns gracefully. Memory is best-effort — it must never crash
    the main execution path.

What a "fact" looks like:
  - "User prefers mcp-qdrant over direct qdrant-client for external tool access."
  - "The mcp-github container uses a distroless image — no shell healthchecks."
  - "qdrant_explicit_memory collection uses 384-dim all-MiniLM-L6-v2 vectors."
  - "ALLOW_WRITE=true must be set for the filesystem MCP to accept write calls."
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from langchain_core.runnables import RunnableConfig

from state.schema import OSState
from core.router import ai_router
from core.memory_client import store_facts

logger = logging.getLogger(__name__)

MEMORY_TIMEOUT = 45  # seconds — memory extraction is non-critical; fail fast

EXTRACTION_PROMPT = """\
You are a memory distillation agent. Your ONLY job is to extract durable, \
reusable facts from the conversation below.

RULES:
1. Output ONLY a newline-separated list of facts. No preamble, no commentary, \
   no numbering, no bullet characters.
2. Each fact must be a single, self-contained declarative sentence (under 25 words).
3. Extract only facts that would be useful in a FUTURE, UNRELATED conversation:
   - User preferences and opinions
   - System configurations that were confirmed correct
   - Tool behaviors and constraints discovered
   - Errors that were diagnosed and their root causes
   - Decisions made about the Nestworks infrastructure
4. Do NOT extract: greetings, acknowledgments, task-specific transient state, \
   or anything that is only true for this specific session.
5. If no durable facts exist in this conversation, output exactly: NO_FACTS

Output 3–5 facts maximum. Fewer is better than padding with trivial observations.\
"""


def _parse_facts(raw: str) -> list[str]:
    """Clean the LLM output into a list of bare fact strings."""
    raw = raw.strip()
    if "NO_FACTS" in raw:
        return []

    lines = raw.splitlines()
    facts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip leading list markers: "1.", "2.", "-", "•", "*"
        line = re.sub(r"^[\d]+\.\s*", "", line)
        line = re.sub(r"^[-•*]\s*", "", line)
        line = line.strip()
        if len(line) > 10:  # ignore single-word or empty outputs
            facts.append(line)
    return facts[:5]  # hard cap — never store more than 5 facts per turn


async def memory_node(state: OSState, config: Optional[RunnableConfig] = None):
    """
    Distill the completed conversation into facts and write them to Qdrant.
    Always returns a minimal state update — never adds to state["messages"].
    """
    thread_id = "unknown"
    if config and "configurable" in config:
        thread_id = config["configurable"].get("thread_id", "unknown")

    # Build a compact representation of the conversation for the LLM
    conversation_lines = []
    for m in state.get("messages", []):
        role = getattr(m, "type", "unknown")
        if role == "ai":
            role = "assistant"
        content = getattr(m, "content", "")
        if content and isinstance(content, str) and content.strip():
            # Truncate very long tool results to prevent context overflow
            if len(content) > 800:
                content = content[:800] + "... [truncated]"
            conversation_lines.append(f"{role.upper()}: {content}")

    if not conversation_lines:
        logger.info("memory_node: no conversation content to distill")
        return {"current_agent": "memory"}

    conversation_text = "\n".join(conversation_lines)

    extraction_messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Extract durable facts from this conversation:\n\n{conversation_text}"
            ),
        },
    ]

    try:
        response = await asyncio.wait_for(
            ai_router.acompletion(
                model="jarvis-local",
                messages=extraction_messages,
                temperature=0.0,   # deterministic — facts are not creative output
                max_tokens=256,
            ),
            timeout=MEMORY_TIMEOUT,
        )
        raw_output = response.choices[0].message.content or ""
        facts = _parse_facts(raw_output)

        if facts:
            stored = await store_facts(
                facts=facts,
                thread_id=thread_id,
                source_agent="memory_node",
            )
            logger.info(
                "memory_node: stored %d/%d facts (thread=%s)",
                stored,
                len(facts),
                thread_id,
            )
        else:
            logger.info("memory_node: no durable facts extracted this turn")

    except asyncio.TimeoutError:
        logger.warning(
            "memory_node: extraction timed out after %ds — skipping", MEMORY_TIMEOUT
        )
    except Exception as exc:
        logger.error("memory_node: unexpected error — %s", exc, exc_info=True)

    # Memory node never modifies messages — it's a silent background write.
    return {"current_agent": "memory"}