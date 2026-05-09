import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.exceptions import SourceLimitExceeded, SourceNotFound
from app.domain.services.source_service import SourceService


def make_service(count=0, source=None):
    repo = AsyncMock()
    repo.count_by_kb.return_value = count
    repo.get.return_value = source
    repo.list_by_kb.return_value = []
    repo.create.return_value = source or MagicMock()

    chunk_repo = AsyncMock()
    chunk_repo.get_pinecone_ids_by_source.return_value = []

    pinecone = MagicMock()

    return SourceService(repo, chunk_repo, pinecone), repo, chunk_repo, pinecone


@pytest.fixture
def kb_id():
    return uuid.uuid4()


@pytest.fixture
def source_id():
    return uuid.uuid4()


@pytest.fixture
def mock_source(source_id, kb_id):
    source = MagicMock()
    source.id = source_id
    source.kb_id = kb_id
    return source


# ── create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_source_succeeds_when_under_limit(kb_id):
    service, repo, _, _ = make_service(count=4)

    await service.create_source(kb_id, "pdf", "s3://bucket/file.pdf")

    repo.create.assert_called_once_with(kb_id, "pdf", "s3://bucket/file.pdf", "fixed")


@pytest.mark.asyncio
async def test_create_source_raises_when_at_limit(kb_id):
    service, _, _, _ = make_service(count=5)  # MAX_SOURCES_PER_KB = 5

    with pytest.raises(SourceLimitExceeded):
        await service.create_source(kb_id, "pdf", "file.pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize("source_type,expected_strategy", [
    ("github", "markdown"),
    ("pdf", "fixed"),
    ("web", "semantic"),
    ("text", "fixed"),
    ("word", "semantic"),
])
async def test_create_source_uses_correct_chunking_strategy(kb_id, source_type, expected_strategy):
    service, repo, _, _ = make_service(count=0)

    await service.create_source(kb_id, source_type, "url")

    _, _, _, strategy = repo.create.call_args[0]
    assert strategy == expected_strategy


@pytest.mark.asyncio
async def test_create_source_unknown_type_defaults_to_fixed(kb_id):
    service, repo, _, _ = make_service(count=0)

    await service.create_source(kb_id, "unknown_type", "url")

    _, _, _, strategy = repo.create.call_args[0]
    assert strategy == "fixed"


# ── list ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sources_returns_repo_result(kb_id):
    service, repo, _, _ = make_service()
    repo.list_by_kb.return_value = [MagicMock(), MagicMock()]

    result = await service.list_sources(kb_id)

    assert len(result) == 2
    repo.list_by_kb.assert_called_once_with(kb_id)


# ── get ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_source_returns_source_when_found(source_id, kb_id, mock_source):
    service, _, _, _ = make_service(source=mock_source)

    result = await service.get_source(source_id, kb_id)

    assert result == mock_source


@pytest.mark.asyncio
async def test_get_source_raises_not_found_when_missing(source_id, kb_id):
    service, _, _, _ = make_service(source=None)

    with pytest.raises(SourceNotFound):
        await service.get_source(source_id, kb_id)


# ── delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_source_deletes_pinecone_vectors_and_source(source_id, kb_id, mock_source):
    service, repo, chunk_repo, pinecone = make_service(source=mock_source)
    chunk_repo.get_pinecone_ids_by_source.return_value = ["vec1", "vec2"]

    await service.delete_source(source_id, kb_id)

    pinecone.delete_by_ids.assert_called_once_with(["vec1", "vec2"])
    repo.delete.assert_called_once_with(source_id)


@pytest.mark.asyncio
async def test_delete_source_skips_pinecone_when_no_chunks(source_id, kb_id, mock_source):
    service, repo, chunk_repo, pinecone = make_service(source=mock_source)
    chunk_repo.get_pinecone_ids_by_source.return_value = []

    await service.delete_source(source_id, kb_id)

    pinecone.delete_by_ids.assert_not_called()
    repo.delete.assert_called_once_with(source_id)


@pytest.mark.asyncio
async def test_delete_source_raises_not_found_when_missing(source_id, kb_id):
    service, _, _, _ = make_service(source=None)

    with pytest.raises(SourceNotFound):
        await service.delete_source(source_id, kb_id)
