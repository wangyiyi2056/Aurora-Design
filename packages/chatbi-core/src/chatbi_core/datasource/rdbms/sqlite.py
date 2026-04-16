from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from chatbi_core.datasource.rdbms.base import RDBMSConnector


class SQLiteConnector(RDBMSConnector):
    def __init__(self, database: str = ":memory:"):
        self._db_type = "sqlite"
        if database == ":memory:":
            self._engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self._engine = create_engine(f"sqlite:///{database}")
