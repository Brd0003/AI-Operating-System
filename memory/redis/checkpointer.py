import os
import json
from typing import Optional, AsyncIterator, Tuple, Sequence, Any
import redis.asyncio as redis
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, ChannelVersions
from langchain_core.runnables import RunnableConfig

REDIS_IP = os.environ.get("INT_IP_REDIS", "172.70.0.180")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

class RedisCheckpointer(BaseCheckpointSaver):
    def __init__(self):
        super().__init__()
        self.redis_client = redis.Redis(
            host=REDIS_IP,
            port=6379,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            db=0,
            decode_responses=True,
            protocol=2
        )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[Tuple[RunnableConfig, Checkpoint, CheckpointMetadata, Optional[dict]]]:
        thread_id = config["configurable"]["thread_id"]
        state_data = await self.redis_client.hget(f"thread:{thread_id}", "state")
        if state_data:
            data = json.loads(state_data)
            return config, data.get("checkpoint"), data.get("metadata", {}), None
        return None

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        payload = json.dumps({"checkpoint": checkpoint, "metadata": metadata}, default=str)
        await self.redis_client.hset(f"thread:{thread_id}", "state", payload)
        return config

    # --- THE FIX THAT PREVENTS THE TIMEOUT CRASH ---
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Asynchronously store intermediate stream writes linked to a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        payload = json.dumps([{"channel": w[0], "value": w[1]} for w in writes], default=str)
        await self.redis_client.hset(f"thread:{thread_id}:writes", task_id, payload)

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