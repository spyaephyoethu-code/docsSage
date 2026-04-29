import tiktoken

# runtime imports
from app.infrastructure.ingestion.base import Chunk
from app.infrastructure.ingestion.chunkers.base import BaseChunker

# type-hint imports
from app.infrastructure.ingestion.base import Document

_CHUNK_SIZE = 512
_OVERLAP = 50


class FixedChunker(BaseChunker):
    def __init__(self, chunk_size: int = _CHUNK_SIZE, overlap: int = _OVERLAP) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc in documents:
            tokens = self._enc.encode(doc.text)
            start = 0
            while start < len(tokens):
                end = min(start + self._chunk_size, len(tokens))
                chunk_tokens = tokens[start:end]
                chunks.append(
                    Chunk(
                        text=self._enc.decode(chunk_tokens),
                        token_count=len(chunk_tokens),
                        metadata=doc.metadata.copy(),
                    )
                )
                if end == len(tokens):
                    break
                start += self._chunk_size - self._overlap
        return chunks
