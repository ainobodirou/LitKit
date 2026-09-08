from typing import Protocol
from app.context.models import Memory


class MemoryRepo(Protocol):
    async def find_relevant(
            self,
            *,
            query_embedding: tuple[float,...],
            limit: int,
    ) -> tuple[Memory, ...]:
        pass

    async def save(
            self,
            *,
            id: str,
            content: str,
            type: str,
            embedding: tuple[float, ...],
            embedding_model: str, 
            source_id: str | None = None 
    ) -> Memory:
        pass

    async def delete(
            self,
            *,
            id: str,
    ) -> None:
        pass



