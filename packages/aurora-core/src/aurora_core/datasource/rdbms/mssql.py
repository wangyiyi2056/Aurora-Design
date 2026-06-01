from urllib.parse import quote_plus

from aurora_core.datasource.rdbms.base import RDBMSConnector


class MSSQLConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1433,
        user: str = "sa",
        password: str = "",
        database: str = "master",
    ):
        pwd = quote_plus(password)
        conn_str = f"mssql+pymssql://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="mssql")
