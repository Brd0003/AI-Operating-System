import os
import json
import uuid
from typing import Optional, AsyncIterator, Tuple, Sequence, Any
from qdrant_client import AsyncQdrantClient, models
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, ChannelVersions
from langchain_core.runnables import RunnableConfig

# Enforcing standard environment variable usage
QDRANT_URL = os.environ.get("URL_QDRANT", "http://172.70.0.152:6333")
COLLECTION_NAME = "langgraph_checkpoints"

class QdrantCheckpointer(BaseCheckpointSaver):
    def __init__(self, url: str = None):
        super().__init__()
        # FIX: Correctly referencing the updated QDRANT_URL variable
        self.client = AsyncQdrantClient(url=url or QDRANT_URL)
        self._collection_initialized = False

    async def _ensure_collection(self):
        """Verify the checkpoint collection exists on Qdrant, using a dummy 1D vector."""
        if not self._collection_initialized:
            if not await self.client.collection_exists(COLLECTION_NAME):
                await self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(size=1, distance=models.Distance.COSINE)
                )
            self._collection_initialized = True

    async def aget_tuple(self, config: RunnableConfig) -> Optional[Tuple[RunnableConfig, Checkpoint, CheckpointMetadata, Optional[dict]]]:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        
        try:
            point_id = str(uuid.UUID(thread_id))
        except ValueError:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))
            
        results = await self.client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_payload=True
        )
        
        if results:
            payload = results[0].payload
            state_data = payload.get("state")
            if state_data:
                data = json.loads(state_data)
                return config, data.get("checkpoint"), data.get("metadata", {}), None
        return None

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        
        try:
            point_id = str(uuid.UUID(thread_id))
        except ValueError:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))

        payload = json.dumps({"checkpoint": checkpoint, "metadata": metadata}, default=str)
        
        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=[0.0],
                    payload={"state": payload}
                )
            ]
        )
        return config

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        
        write_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{thread_id}:writes:{task_id}"))
        payload = json.dumps([{"channel": w[0], "value": w[1]} for w in writes], default=str)
        
        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=write_id,
                    vector=[0.0],
                    payload={"task_id": task_id, "thread_id": thread_id, "writes": payload}
                )
            ]
        )

    def get_tuple(self, config: RunnableConfig):
        raise NotImplementedError("Use aget_tuple asynchronously")
        
    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions):
        raise NotImplementedError("Use aput asynchronously")
        
    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = ""):
        raise NotImplementedError("Use aput_writes asynchronously")

    def list(self, config, *, filter=None, before=None, limit=None) -> AsyncIterator[Tuple[RunnableConfig, Checkpoint, CheckpointMetadata, Optional[dict]]]:
        raise NotImplementedError()
        
    async def alist(self, config, *, filter=None, before=None, limit=None) -> AsyncIterator[Tuple[RunnableConfig, Checkpoint, CheckpointMetadata, Optional[dict]]]:
        if False: yield