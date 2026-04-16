from chatbi_core.datasource.rdbms.base import RDBMSConnector


class DuckDBConnector(RDBMSConnector):
    def __init__(self, database: str = ":memory:"):
        super().__init__(f"duckdb:///{database}", db_type="duckdb")
