import re

import tiktoken

# runtime imports
from app.infrastructure.ingestion.base import Chunk
from app.infrastructure.ingestion.chunkers.base import BaseChunker

# type-hint imports
from app.infrastructure.ingestion.base import Document

_MAX_TOKENS = 512
_HEADER_RE = re.compile(r"\n(?=#{1,6}\s)")


class MarkdownChunker(BaseChunker):
    """Split on headers first, then paragraphs for sections that exceed max_tokens."""

    def __init__(self, max_tokens: int = _MAX_TOKENS) -> None:
        self._max_tokens = max_tokens
        self._enc = tiktoken.get_encoding("cl100k_base")

    def _tok(self, text: str) -> int:
        return len(self._enc.encode(text))

    def chunk(self, documents: list[Document]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc in documents:
            sections = [s.strip() for s in _HEADER_RE.split(doc.text) if s.strip()]
            for section in sections:
                if self._tok(section) <= self._max_tokens:
                    chunks.append(
                        Chunk(
                            text=section,
                            token_count=self._tok(section),
                            metadata=doc.metadata.copy(),
                        )
                    )
                else:
                    paragraphs = [p.strip() for p in re.split(r"\n\n+", section) if p.strip()]
                    current = ""
                    for para in paragraphs:
                        candidate = f"{current}\n\n{para}".strip() if current else para
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
                            current = para
                    if current:
                        chunks.append(
                            Chunk(
                                text=current,
                                token_count=self._tok(current),
                                metadata=doc.metadata.copy(),
                            )
                        )
        return chunks
