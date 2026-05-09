import uuid

import pytest

from app.infrastructure.retrieval.types import RetrievedChunk


@pytest.fixture
def kb_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(pinecone_id="a", chunk_text="database connection timeout error", rank_score=0.9),
        RetrievedChunk(pinecone_id="b", chunk_text="how to configure the database", rank_score=0.8),
        RetrievedChunk(pinecone_id="c", chunk_text="timeout settings for the server", rank_score=0.7),
    ]
