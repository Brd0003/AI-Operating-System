import asyncio
import os

from langchain_mcp_adapters.client import MultiServerMCPClient


async def initialize_agent_tools():
    """Load MCP tools from independent services without failing all discovery."""

    qdrant_url = os.environ.get(
        "QDRANT_MCP_URL",
        "http://mcp-qdrant:8000",
    )
    filesystem_url = os.environ.get(
        "FILESYSTEM_MCP_URL",
        "http://mcp-filesystem:8000",
    )
    github_url = os.environ.get(
        "GITHUB_MCP_URL",
        "http://mcp-github:8000",
    )
    github_token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")

    connections = {
        "qdrant": {
            "transport": "sse",
            "url": f"{qdrant_url.rstrip('/')}/sse",
            "headers": {
                "Host": "localhost:8000",
            },
        },
        "filesystem": {
            "transport": "sse",
            "url": f"{filesystem_url.rstrip('/')}/sse",
        },
    }

    if github_token:
        connections["github"] = {
            "transport": "streamable_http",
            "url": f"{github_url.rstrip('/')}/mcp",
            "headers": {
                "Authorization": f"Bearer {github_token}",
            },
        }
    else:
        print(
            "⚠️ GITHUB_PERSONAL_ACCESS_TOKEN is not set; "
            "skipping GitHub MCP tool discovery.",
            flush=True,
        )

    client = MultiServerMCPClient(connections)

    results = await asyncio.gather(
        *(client.get_tools(server_name=name) for name in connections),
        return_exceptions=True,
    )

    all_tools = []

    for name, result in zip(connections, results):
        if isinstance(result, BaseException):
            print(
                f"⚠️ Warning: MCP server '{name}' failed to load; "
                f"continuing without it: {result!r}",
                flush=True,
            )
            continue

        all_tools.extend(result)
        print(
            f"✅ Loaded {len(result)} tool(s) from '{name}'.",
            flush=True,
        )

    print(
        f"✅ MCP discovery complete: {len(all_tools)} total tool(s) available.",
        flush=True,
    )

    return all_tools