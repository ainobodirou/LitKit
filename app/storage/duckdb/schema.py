import duckdb

MEMORIES_SCHEMA = "CREATE TABLE IF NOT EXISTS memories(\
            id VARCHAR PRIMARY KEY, \
            content VARCHAR NOT NULL, \
            type VARCHAR NOT NULL, \
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL, \
            embedding FLOAT[384] NOT NULL, \
            embedding_model VARCHAR NOT NULL, \
            source_id VARCHAR \
            );"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(MEMORIES_SCHEMA)
