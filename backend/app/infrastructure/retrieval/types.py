from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    pinecone_id: str
    chunk_text: str
    rank_score: float
    source_url: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_title: str | None = None
