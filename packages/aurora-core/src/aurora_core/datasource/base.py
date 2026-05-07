from abc import ABC, abstractmethod
from typing import Dict, List, Tuple


class BaseConnector(ABC):
    @property
    @abstractmethod
    def db_type(self) -> str:
        """Return database type identifier."""

    @abstractmethod
    def get_table_names(self) -> List[str]:
        """Return list of table names."""

    @abstractmethod
    def get_table_schema(self, table: str) -> str:
        """Return DDL or schema description for a table."""

    @abstractmethod
    def query(self, sql: str) -> List[Dict]:
        """Execute a SELECT query and return results."""

    @abstractmethod
    def run(self, sql: str) -> Tuple[bool, str]:
        """Execute SQL and return (success, result_or_error)."""
