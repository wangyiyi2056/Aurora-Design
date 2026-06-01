from urllib.parse import quote_plus

from aurora_core.datasource.rdbms.base import RDBMSConnector


class OracleConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1521,
        user: str = "system",
        password: str = "",
        database: str = "ORCL",
        service_name: str = "",
    ):
        pwd = quote_plus(password)
        if service_name:
            conn_str = (
                f"oracle+oracledb://{user}:{pwd}@{host}:{port}"
                f"/?service_name={service_name}"
            )
        else:
            conn_str = f"oracle+oracledb://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="oracle")
