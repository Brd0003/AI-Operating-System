import os
import json
import uuid
from typing import Optional, AsyncIterator, Iterator, Tuple, Sequence, Any
from qdrant_client import AsyncQdrantClient, models
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from langchain_core.runnables import RunnableConfig

COLLECTION_NAME = "langgraph_checkpoints"

class QdrantCheckpointer(BaseCheckpointSaver):
    """LangGraph checkpointer backed by Qdrant (Payload Accelerated)."""

    def __init__(self, url: str = None):
        super().__init__()
        qdrant_url = url or os.environ.get("URL_QDRANT")
        if not qdrant_url:
            raise RuntimeError(
                "URL_QDRANT is not set. The system-agent cannot start without a "
                "Qdrant endpoint for checkpointing. Check your .env file."
            )
        self.client = AsyncQdrantClient(url=qdrant_url)
        self._collection_initialized = False

    async def _ensure_collection(self) -> None:
        if self._collection_initialized:
            return
        if not await self.client.collection_exists(COLLECTION_NAME):
            await self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=1, distance=models.Distance.COSINE
                ),
            )
        self._collection_initialized = True

    @staticmethod
    def _point_id(thread_id: str) -> str:
        try:
            return str(uuid.UUID(thread_id))
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))

    @staticmethod
    def _write_id(thread_id: str, task_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{thread_id}:writes:{task_id}"))

    def get_next_version(self, current: Optional[int], channel: Any) -> int:
        return 1 if current is None else current + 1

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        point_id = self._point_id(thread_id)
        results = await self.client.retrieve(collection_name=COLLECTION_NAME, ids=[point_id], with_payload=True)
        if not results:
            return None
        payload = results[0].payload or {}
        state_data = payload.get("state")
        if not state_data:
            return None
        try:
            data = json.loads(state_data)
        except Exception:
            return None
        return CheckpointTuple(
            config=config, 
            checkpoint=data.get("checkpoint", {}), 
            metadata=data.get("metadata", {})
        )

    async def alist(self, config: Optional[RunnableConfig], *, filter: Optional[dict] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        # NOTE: alist is intentionally a no-op stub. LangGraph calls this for
        # checkpoint history; an empty result means rewind/fork features will
        # silently return nothing. Implement if those features are needed.
        return
        yield

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        point_id = self._point_id(thread_id)
        # Serialize using default=str as a safe fallback; channel values with
        # non-serializable objects are stringified intentionally to avoid corruption
        try:
            payload = json.dumps({"checkpoint": checkpoint, "metadata": metadata}, default=str)
        except Exception:
            payload = json.dumps({"checkpoint": {}, "metadata": {}}, default=str)
        await self.client.upsert(collection_name=COLLECTION_NAME, points=[models.PointStruct(id=point_id, vector=[0.0], payload={"state": payload})])
        return config

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[Tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        write_id = self._write_id(thread_id, task_id)
        try:
            payload = json.dumps([{"channel": w[0], "value": w[1]} for w in writes], default=str)
        except Exception:
            payload = "[]"
        await self.client.upsert(collection_name=COLLECTION_NAME, points=[models.PointStruct(id=write_id, vector=[0.0], payload={"task_id": task_id, "thread_id": thread_id, "writes": payload})])

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]: raise NotImplementedError()
    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig: raise NotImplementedError()
    def alist(self, config: Optional[RunnableConfig] = None, *, filter: Optional[dict] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]: raise NotImplementedError()
