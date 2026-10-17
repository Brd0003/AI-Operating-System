import os
import uuid
from typing import List, Optional
from qdrant_client import AsyncQdrantClient, models
from fastembed import TextEmbedding
import asyncio

COLLECTION_NAME = "semantic_memory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384

_embedder: Optional[TextEmbedding] = None
_qdrant_client: Optional[AsyncQdrantClient] = None
_lock = asyncio.Lock()
_collection_ready = False


def _get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _embedder


async def _get_qdrant_client() -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        url = os.environ.get("URL_QDRANT")
        if not url:
            raise RuntimeError("URL_QDRANT is not set — memory client cannot connect to Qdrant.")
        _qdrant_client = AsyncQdrantClient(url=url)
    return _qdrant_client


async def _ensure_collection() -> None:
    global _collection_ready
    if _collection_ready:
        return
    async with _lock:
        if _collection_ready:
            return
        client = await _get_qdrant_client()
        if not await client.collection_exists(COLLECTION_NAME):
            await client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )
        _collection_ready = True


async def _embed(text: str) -> List[float]:
    # Run blocking embed in thread to avoid blocking event loop
    loop = asyncio.get_running_loop()
    embedder = _get_embedder()
    vectors = await loop.run_in_executor(None, lambda: list(embedder.embed([text])))
    return vectors[0].tolist() if vectors else []


async def store_facts(facts: List[str], thread_id: Optional[str] = None) -> None:
    if not facts:
        return
    await _ensure_collection()
    client = await _get_qdrant_client()
    vectors = []
    for fact in facts:
        vec = await _embed(fact)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{thread_id or 'global'}:{fact}"))
        vectors.append(
            models.PointStruct(
                id=point_id,
                vector=vec,
                payload={
                    "fact": fact,
                    "thread_id": thread_id or "global",
                },
            )
        )
    if vectors:
        await client.upsert(collection_name=COLLECTION_NAME, points=vectors)


async def retrieve_relevant(query: str, top_k: int = 5) -> List[str]:
    if not query:
        return []
    try:
        await _ensure_collection()
        client = await _get_qdrant_client()
        qvec = await _embed(query)
        # Prefer query_points (newer API); fall back to search if needed
        try:
            results = await client.query_points(
                collection_name=COLLECTION_NAME,
                query=qvec,
                limit=top_k,
                with_payload=True,
            )
            points = results.points
        except Exception:
            # Fallback to deprecated search
            results = await client.search(
                collection_name=COLLECTION_NAME,
                query_vector=qvec,
                limit=top_k,
                with_payload=True,
            )
            points = results
        facts: List[str] = []
        for p in points:
            payload = getattr(p, "payload", {}) or {}
            if payload.get("fact"):
                facts.append(payload["fact"])
        return facts
    except Exception:
        return []
