from urllib.parse import quote_plus

from chatbi_core.datasource.rdbms.base import RDBMSConnector


class PostgreSQLConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "postgres",
    ):
        pwd = quote_plus(password)
        conn_str = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="postgresql")
