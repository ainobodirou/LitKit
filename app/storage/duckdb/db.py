import duckdb
from app.storage.duckdb.schema import create_schema

class DuckDBDatabase :
    def __init__(
            self,
            *,
            path: str,    
    ) -> None: 
        self.path = path
        self.conn = duckdb.connect(path)
        create_schema(conn=self.conn)

    def close_conn(self) -> None:
        self.conn.close()
