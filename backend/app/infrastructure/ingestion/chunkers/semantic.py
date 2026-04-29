import re

import tiktoken

# runtime imports
from app.infrastructure.ingestion.base import Chunk
from app.infrastructure.ingestion.chunkers.base import BaseChunker

# type-hint imports
from app.infrastructure.ingestion.base import Document

_MAX_TOKENS = 512
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class SemanticChunker(BaseChunker):
    """
    Groups sentences into chunks up to max_tokens, using paragraph breaks
    as hard boundaries.
    """

    def __init__(self, max_tokens: int = _MAX_TOKENS) -> None:
        self._max_tokens = max_tokens
        self._enc = tiktoken.get_encoding("cl100k_base")

    def _tok(self, text: str) -> int:
        return len(self._enc.encode(text))

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc in documents:
            paragraphs = [p.strip() for p in re.split(r"\n\n+", doc.text) if p.strip()]
            for para in paragraphs:
                sentences = [s.strip() for s in _SENTENCE_RE.split(para) if s.strip()]
                current = ""
                for sentence in sentences:
                    candidate = f"{current} {sentence}".strip() if current else sentence
                    if self._tok(candidate) <= self._max_tokens:
                        current = candidate
                    else:
                        if current:
                            chunks.append(
                                Chunk(
                                    text=current,
                                    token_count=self._tok(current),
                                    metadata=doc.metadata.copy(),
                                )
                            )
                        current = sentence
                if current:
                    chunks.append(
                        Chunk(
                            text=current,
                            token_count=self._tok(current),
                            metadata=doc.metadata.copy(),
                        )
                    )
        return chunks
