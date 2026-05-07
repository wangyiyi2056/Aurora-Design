from pathlib import Path
from typing import List

from aurora_ext.rag.knowledge.base import BaseKnowledge, Document


class FileKnowledge(BaseKnowledge):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        path = Path(self.file_path)
        text = path.read_text(encoding="utf-8")
        return [Document(content=text, metadata={"source": str(path)})]


class KnowledgeFactory:
    @staticmethod
    def from_file_path(file_path: str) -> BaseKnowledge:
        return FileKnowledge(file_path)
