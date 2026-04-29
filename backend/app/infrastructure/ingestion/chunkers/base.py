from abc import ABC, abstractmethod

# type-hint imports
from app.infrastructure.ingestion.base import Chunk, Document


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, documents: list[Document]) -> list[Chunk]:
        ...
