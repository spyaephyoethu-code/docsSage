import re

# runtime imports
from app.domain.schemas.chat import CitationItem

# type-hint imports
from app.infrastructure.retrieval.types import RetrievedChunk


def parse_citations(answer: str, chunks: list[RetrievedChunk]) -> list[CitationItem]:
    used = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    return [
        CitationItem(
            index=i,
            chunk_text=chunk.chunk_text[:500],
            source_name=chunk.source_title,
            source_url=chunk.source_url,
            source_type=chunk.source_type,
        )
        for i, chunk in enumerate(chunks, start=1)
        if i in used
    ]
