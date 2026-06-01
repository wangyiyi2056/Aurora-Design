from urllib.parse import quote_plus

from aurora_core.datasource.rdbms.base import RDBMSConnector


class ClickHouseConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
    ):
        pwd = quote_plus(password)
        conn_str = f"clickhousedb://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="clickhouse")
