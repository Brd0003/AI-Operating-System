import os
import httpx
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient

# --- NEW: Required Qdrant models for building collections ---
from qdrant_client.http.models import Distance, VectorParams

mcp = FastMCP("Qdrant Memory Server")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = os.environ.get(
    "COLLECTION_NAME",
    "qdrant_explicit_memory",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
LITELLM_BASE_URL = os.environ.get(
    "LITELLM_BASE_URL",
    "http://172.70.0.165:4000/v1",
)
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")
EMBED_MODEL = os.environ.get(
    "EMBED_MODEL",
    "ollama/nomic-embed-text:v1.5",
)

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
)

# --- THE FIX: SELF-HEALING INITIALIZATION ---
def ensure_collection_exists():
    """Verify the explicit memory collection exists and build it if missing."""
    try:
        if not client.collection_exists(COLLECTION_NAME):
            print(f"⚠️ Collection '{COLLECTION_NAME}' not found. Initializing...", flush=True)
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(f"✅ Collection '{COLLECTION_NAME}' successfully created.", flush=True)
        else:
            print(f"✅ Collection '{COLLECTION_NAME}' verified and ready.", flush=True)
    except Exception as e:
        print(f"❌ Failed to verify or create Qdrant collection: {e}", flush=True)

# Run the check immediately when the container script starts
ensure_collection_exists()


async def _embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            f"{LITELLM_BASE_URL.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={
                "model": EMBED_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


@mcp.tool()
async def search_memory(query: str, limit: int = 3) -> str:
    """Search the explicit-memory Qdrant vector database."""
    try:
        vector = await _embed(query)

        hits = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
        ).points

        if not hits:
            return "No relevant memory found."

        return "\n".join(
            f"- {hit.payload.get('text', hit.payload)} "
            f"(score={hit.score:.2f})"
            for hit in hits
        )
    except Exception as exc:
        return f"Error querying explicit memory: {exc}"


async def fetch_explicit_memory(user_input: str) -> str:
    """Retrieve relevant explicit memory without round-tripping through MCP."""
    return await search_memory(user_input)


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("FASTMCP_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("FASTMCP_SERVER_PORT", "8000"))

    uvicorn.run(
        mcp.sse_app(),
        host=host,
        port=port,
    )