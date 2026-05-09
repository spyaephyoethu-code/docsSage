import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.exceptions import KBLimitExceeded, KBNotFound
from app.domain.schemas.kb import KBCreate, KBUpdate
from app.domain.services.kb_service import KBService


def make_service(count=0, kb=None):
    repo = AsyncMock()
    repo.count_by_user.return_value = count
    repo.get_owned.return_value = kb
    repo.list_by_user.return_value = []
    repo.create.return_value = kb or MagicMock()
    repo.update.return_value = kb or MagicMock()

    chunk_repo = AsyncMock()
    chunk_repo.get_pinecone_ids_by_kb.return_value = []

    pinecone = MagicMock()

    return KBService(repo, chunk_repo, pinecone), repo, chunk_repo, pinecone


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def kb_id():
    return uuid.uuid4()


@pytest.fixture
def mock_kb(kb_id, user_id):
    kb = MagicMock()
    kb.id = kb_id
    kb.user_id = user_id
    return kb


# ── list ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_kbs_returns_repo_result(user_id):
    service, repo, _, _ = make_service()
    repo.list_by_user.return_value = [MagicMock(), MagicMock()]

    result = await service.list_kbs(user_id)

    assert len(result) == 2
    repo.list_by_user.assert_called_once_with(user_id)


# ── get ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_kb_returns_kb_when_found(user_id, kb_id, mock_kb):
    service, repo, _, _ = make_service(kb=mock_kb)

    result = await service.get_kb(kb_id, user_id)

    assert result == mock_kb


@pytest.mark.asyncio
async def test_get_kb_raises_not_found_when_missing(user_id, kb_id):
    service, repo, _, _ = make_service(kb=None)

    with pytest.raises(KBNotFound):
        await service.get_kb(kb_id, user_id)


# ── create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_kb_succeeds_when_under_limit(user_id):
    service, repo, _, _ = make_service(count=2)
    body = KBCreate(name="My KB")

    await service.create_kb(user_id, body)

    repo.create.assert_called_once_with(user_id, "My KB", None)


@pytest.mark.asyncio
async def test_create_kb_raises_when_at_limit(user_id):
    service, _, _, _ = make_service(count=3)  # MAX_KBS_PER_USER = 3
    body = KBCreate(name="One too many")

    with pytest.raises(KBLimitExceeded):
        await service.create_kb(user_id, body)


# ── update ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_kb_calls_repo_update(user_id, kb_id, mock_kb):
    service, repo, _, _ = make_service(kb=mock_kb)
    body = KBUpdate(name="New name")

    await service.update_kb(kb_id, user_id, body)

    repo.update.assert_called_once_with(mock_kb, "New name", None)


@pytest.mark.asyncio
async def test_update_kb_raises_not_found_when_missing(user_id, kb_id):
    service, _, _, _ = make_service(kb=None)
    body = KBUpdate(name="New name")

    with pytest.raises(KBNotFound):
        await service.update_kb(kb_id, user_id, body)


# ── delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_kb_deletes_pinecone_vectors_and_kb(user_id, kb_id, mock_kb):
    service, repo, chunk_repo, pinecone = make_service(kb=mock_kb)
    chunk_repo.get_pinecone_ids_by_kb.return_value = ["id1", "id2"]

    await service.delete_kb(kb_id, user_id)

    pinecone.delete_by_ids.assert_called_once_with(["id1", "id2"])
    repo.delete.assert_called_once_with(mock_kb)


@pytest.mark.asyncio
async def test_delete_kb_skips_pinecone_when_no_chunks(user_id, kb_id, mock_kb):
    service, repo, chunk_repo, pinecone = make_service(kb=mock_kb)
    chunk_repo.get_pinecone_ids_by_kb.return_value = []

    await service.delete_kb(kb_id, user_id)

    pinecone.delete_by_ids.assert_not_called()
    repo.delete.assert_called_once_with(mock_kb)


@pytest.mark.asyncio
async def test_delete_kb_raises_not_found_when_missing(user_id, kb_id):
    service, _, _, _ = make_service(kb=None)

    with pytest.raises(KBNotFound):
        await service.delete_kb(kb_id, user_id)
