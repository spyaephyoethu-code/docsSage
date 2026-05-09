import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.vector_store.pinecone_client import PineconeClient


@pytest.fixture
def client() -> PineconeClient:
    with patch("app.infrastructure.vector_store.pinecone_client.settings") as mock_settings, \
         patch("app.infrastructure.vector_store.pinecone_client.Pinecone") as mock_pinecone:
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_index_name = "test-index"
        mock_pinecone.return_value.Index.return_value = MagicMock()
        return PineconeClient()


def test_query_returns_retrieved_chunks(client):
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()

    match = MagicMock()
    match.id = "chunk_abc"
    match.score = 0.92
    match.metadata = {
        "chunk_text": "database connection timeout",
        "source_type": "github",
        "source_id": str(uuid.uuid4()),
        "source_title": "README.md",
        "url": "https://github.com/org/repo/README.md",
    }

    client._index.query.return_value = MagicMock(matches=[match])

    results = client.query(kb_id=kb_id, user_id=user_id, vector=[0.1] * 512)

    assert len(results) == 1
    assert results[0].pinecone_id == "chunk_abc"
    assert results[0].rank_score == pytest.approx(0.92)
    assert results[0].chunk_text == "database connection timeout"


def test_query_filters_by_kb_and_user(client):
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()

    client._index.query.return_value = MagicMock(matches=[])

    client.query(kb_id=kb_id, user_id=user_id, vector=[0.0] * 512)

    call_kwargs = client._index.query.call_args[1]
    assert call_kwargs["filter"]["kb_id"] == str(kb_id)
    assert call_kwargs["filter"]["user_id"] == str(user_id)


def test_query_empty_results_returns_empty_list(client):
    client._index.query.return_value = MagicMock(matches=[])

    results = client.query(kb_id=uuid.uuid4(), user_id=uuid.uuid4(), vector=[0.0] * 512)

    assert results == []


def test_upsert_chunks_batches_correctly(client):
    kb_id = uuid.uuid4()
    source_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 150 chunks — should produce 2 batches (100 + 50)
    n = 150
    client.upsert_chunks(
        kb_id=kb_id,
        source_id=source_id,
        source_type="pdf",
        user_id=user_id,
        chunk_ids=[str(i) for i in range(n)],
        embeddings=[[0.1] * 512 for _ in range(n)],
        texts=[f"chunk text {i}" for i in range(n)],
        metadatas=[{} for _ in range(n)],
    )

    assert client._index.upsert.call_count == 2


def test_upsert_chunks_includes_required_metadata(client):
    kb_id = uuid.uuid4()
    source_id = uuid.uuid4()
    user_id = uuid.uuid4()

    client.upsert_chunks(
        kb_id=kb_id,
        source_id=source_id,
        source_type="pdf",
        user_id=user_id,
        chunk_ids=["chunk1"],
        embeddings=[[0.1] * 512],
        texts=["some chunk text"],
        metadatas=[{"page_num": 2}],
    )

    vectors = client._index.upsert.call_args[1]["vectors"]
    meta = vectors[0]["metadata"]
    assert meta["kb_id"] == str(kb_id)
    assert meta["user_id"] == str(user_id)
    assert meta["source_type"] == "pdf"
    assert meta["chunk_text"] == "some chunk text"
    assert meta["page_num"] == 2


def test_delete_by_ids_calls_index_delete(client):
    ids = ["a", "b", "c"]
    client.delete_by_ids(ids)
    client._index.delete.assert_called_once_with(ids=ids)
