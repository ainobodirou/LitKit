from duckdb import DuckDBPyConnection
from app.context.models import Memory


class DuckDBMemoryRepo: 
    def __init__(
            self,
            *,
            conn: DuckDBPyConnection,
    ) -> None:
        self.conn = conn

    async def save(self, *, id: str, content:str , type: str, embedding: tuple[float,...], embedding_model: str, source_id: str | None = None) -> Memory:
        query = "INSERT INTO Memories (id, content, type, embedding, embedding_model, source_id) \
                 VALUES ($id, $content, $type, $embedding, $embedding_model, $source_id)\
                 RETURNING id, content, type, created_at, source_id;"
        
        row = self.conn.execute(query, {
            "id": id,
            "content": content,
            "type": type,
            "embedding": embedding,
            "embedding_model": embedding_model,
            "source_id": source_id
            })
        
        memo = row.fetchone()
        return Memory(
            id = memo[0],
            content = memo[1],
            type = memo[2],
            created_at = memo[3],
            source_id = memo[4],
        )

    async def delete(self, *, id: str) -> None:
        self.conn.execute("DELETE FROM Memories \
                           WHERE id = $id", {"id": id})


        

