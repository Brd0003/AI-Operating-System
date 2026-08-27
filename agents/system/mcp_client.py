import asyncio
import os
import shutil

from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_TOOL_MANIFEST: dict[str, list[str]] = {}

async def initialize_agent_tools():
    """Load all MCP tools natively using ultra-fast stdio transports."""

    fs_command = shutil.which("rust-mcp-filesystem") or "rust-mcp-filesystem"
    uvx_command = shutil.which("uvx") or "uvx"
    npx_command = shutil.which("npx") or "npx"
    snippets_command = shutil.which("mcp-code-snippets") or "mcp-code-snippets"

    # CRITICAL FIX: Inherit the Docker container's base environment
    base_env = os.environ.copy()

    # Construct Qdrant Env
    qdrant_env = base_env.copy()
    qdrant_env.update({
        "QDRANT_URL": os.environ.get("URL_QDRANT", "http://172.70.0.152:6333"),
        "COLLECTION_NAME": "qdrant_explicit_memory",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "HF_TOKEN": os.environ.get("HF_TOKEN", ""),
    })

    # Construct Code Snippets Env
    snippets_env = base_env.copy()
    snippets_env.update({
        "MCP_PROXY_CONFIG": "/app/mcp_proxy.json",
        "PROJECT_ROOT_PATH": "/projects",
    })

    connections = {
        "filesystem": {
            "transport": "stdio",
            "command": fs_command,
            "args": ["/projects"],
            "env": base_env
        },
        "qdrant": {
            "transport": "stdio",
            "command": uvx_command,
            "args": ["mcp-server-qdrant"],
            "env": qdrant_env
        },
        "code-snippets": {
            "transport": "stdio",
            "command": snippets_command,
            "args": [],
            "env": snippets_env
        }
    }

    github_token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if github_token:
        github_env = base_env.copy()
        github_env["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
        connections["github"] = {
            "transport": "stdio",
            "command": npx_command,
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": github_env
        }
    else:
        print("⚠️ GITHUB_PERSONAL_ACCESS_TOKEN is not set; skipping GitHub MCP.", flush=True)

    try:
        client = MultiServerMCPClient(connections)
    except Exception as e:
        print(f"❌ Failed to initialize MultiServerMCPClient: {e}", flush=True)
        return []

    results = await asyncio.gather(
        *(client.get_tools(server_name=name) for name in connections),
        return_exceptions=True,
    )

    all_tools = []

    for name, result in zip(connections, results):
        if isinstance(result, BaseException):
            print(f"⚠️ Warning: Native MCP server '{name}' failed to load: {result!r}", flush=True)
            continue

        all_tools.extend(result)
        MCP_TOOL_MANIFEST[name] = [getattr(t, "name", str(t)) for t in result]
        print(f"✅ Loaded {len(result)} tool(s) natively from '{name}' via stdio.", flush=True)

    print(f"✅ Fast MCP discovery complete: {len(all_tools)} total tool(s) bound natively.", flush=True)

    return all_tools