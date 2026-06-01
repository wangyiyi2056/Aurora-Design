from urllib.parse import quote_plus

from aurora_core.datasource.rdbms.base import RDBMSConnector


class StarRocksConnector(RDBMSConnector):
    """StarRocks uses the MySQL wire protocol."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9030,
        user: str = "root",
        password: str = "",
        database: str = "default",
    ):
        pwd = quote_plus(password)
        conn_str = f"starrocks://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="starrocks")
