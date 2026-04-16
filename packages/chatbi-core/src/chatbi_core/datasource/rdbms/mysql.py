from urllib.parse import quote_plus

from chatbi_core.datasource.rdbms.base import RDBMSConnector


class MySQLConnector(RDBMSConnector):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "mysql",
    ):
        pwd = quote_plus(password)
        conn_str = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{database}"
        super().__init__(conn_str, db_type="mysql")
