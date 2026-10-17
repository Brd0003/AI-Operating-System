"""
core/mcp_tools.py — lazy MCP tool loader for the system-agent swarm.

Connects to the four MCP servers on the internal bridge network and returns
a flat list of LangChain-compatible tools.  Connection is established once
per process and cached; individual server failures are logged and skipped
rather than crashing the whole agent.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

# ── MCP server URLs from environment (all on the nestworks internal bridge) ──
_SERVER_CONFIG: dict[str, dict[str, Any]] = {
    "filesystem": {
        "url": os.environ.get("URL_MCP_FILESYSTEM", ""),
        "transport": "streamable_http",
    },
    "qdrant": {
        "url": os.environ.get("URL_MCP_QDRANT", ""),
        "transport": "streamable_http",
    },
    "github": {
        "url": os.environ.get("URL_MCP_GITHUB", ""),
        "transport": "streamable_http",
    },
    "code_snippets": {
        "url": os.environ.get("URL_MCP_CODE_SNIPPETS", ""),
        "transport": "streamable_http",
    },
}

_tools_cache: list | None = None


async def get_tools() -> list:
    """Return cached MCP tools, connecting on first call."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    # Only include servers that have a URL configured
    active_servers = {
        name: cfg for name, cfg in _SERVER_CONFIG.items() if cfg["url"]
    }

    if not active_servers:
        logger.warning("mcp_tools: no MCP server URLs configured — tool calls disabled")
        _tools_cache = []
        return _tools_cache

    try:
        client = MultiServerMCPClient(active_servers)
        _tools_cache = await client.get_tools()
        logger.info(
            "mcp_tools: loaded %d tools from servers: %s",
            len(_tools_cache),
            list(active_servers.keys()),
        )
    except Exception as exc:
        logger.error("mcp_tools: failed to load tools — %s", exc)
        _tools_cache = []

    return _tools_cache
