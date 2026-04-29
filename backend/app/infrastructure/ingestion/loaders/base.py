from abc import ABC, abstractmethod

# type-hint imports
from app.infrastructure.ingestion.base import Document


class BaseLoader(ABC):
    @abstractmethod
    async def load(self, url_or_path: str) -> list[Document]:
        ...
