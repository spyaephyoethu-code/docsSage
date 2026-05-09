from app.infrastructure.retrieval.types import RetrievedChunk


def rrf_merge(
    dense: list[RetrievedChunk],
    sparse: list[RetrievedChunk],
    k: int = 60,
    top_n: int = 20,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion over two ranked lists, deduplicated by pinecone_id."""
    scores: dict[str, float] = {}
    by_id: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(dense, start=1):
        scores[chunk.pinecone_id] = scores.get(chunk.pinecone_id, 0.0) + 1.0 / (
            k + rank
        )
        by_id[chunk.pinecone_id] = chunk

    for rank, chunk in enumerate(sparse, start=1):
        scores[chunk.pinecone_id] = scores.get(chunk.pinecone_id, 0.0) + 1.0 / (
            k + rank
        )
        if chunk.pinecone_id not in by_id:
            by_id[chunk.pinecone_id] = chunk

    ranked = sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)[:top_n]
    result = []
    for pid in ranked:
        chunk = by_id[pid]
        chunk.rank_score = scores[pid]
        result.append(chunk)
    return result
