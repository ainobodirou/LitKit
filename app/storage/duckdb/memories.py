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

    ## Query DB based on cosine similarity
    async def find_relevant(self, *, embedding_model: str, query_embedding: tuple[float,...], limit: int) -> tuple[Memory,...]:

        ## Validate Query and Limit
        if limit < 0:
            raise ValueError(f"DuckDB semantic lookup: Negative limit: {limit}")
        elif limit == 0:
            return ()
        elif len(query_embedding) != 384:
            raise ValueError(f"DuckDB semantic lookup: Invalid query dimensions, should be 384, is: {len(query_embedding)}")
        ## Assemeble and query with cosine similarity
        query = "SELECT id, content, type, created_at,  array_cosine_similarity(embedding, CAST($query_embedding AS FLOAT[384])) AS relevance, source_id \
        FROM Memories \
        WHERE embedding_model = $embedding_model \
        ORDER BY relevance DESC, created_at DESC \
        LIMIT $limit \
        "
        result = self.conn.execute(query, {"query_embedding": query_embedding,
                                            "limit" : limit,
                                            "embedding_model": embedding_model}).fetchall()
        memories = []
        for row in result:
            memory = Memory(
                id = row[0],
                content=row[1],
                type = row[2],
                created_at=row[3],
                relevance = row[4],
                source_id=row[5]
            )
            memories.append(memory)
        return tuple(memories)
    



        

