from aurora_core.datasource.rdbms.base import RDBMSConnector


class HiveConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 10000,
        user: str = "hive",
        password: str = "",
        database: str = "default",
    ):
        conn_str = f"hive://{user}:{password}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="hive")
