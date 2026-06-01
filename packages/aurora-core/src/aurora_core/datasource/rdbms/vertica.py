from urllib.parse import quote_plus

from aurora_core.datasource.rdbms.base import RDBMSConnector


class VerticaConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5433,
        user: str = "dbadmin",
        password: str = "",
        database: str = "VMart",
    ):
        pwd = quote_plus(password)
        conn_str = f"vertica+vertica_python://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="vertica")
