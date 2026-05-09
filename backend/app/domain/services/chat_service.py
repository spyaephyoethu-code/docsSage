import asyncio
import logging
import time
import uuid

# runtime imports
from app.core.quotas import MAX_CHAT_MESSAGES_PER_DAY
from app.domain.exceptions import (
    BudgetExceeded,
    ConversationNotFound,
    DailyLimitExceeded,
)
from app.domain.schemas.chat import ChatResponse, StreamDoneEvent, StreamErrorEvent, StreamTokenEvent
from app.domain.utils.citation import parse_citations

# type-hint imports
from app.domain.schemas.chat import CitationItem
from app.infrastructure.db.repositories.conversation_repository import (
    ConversationRepository,
)
from app.infrastructure.db.repositories.message_repository import MessageRepository
from app.infrastructure.embeddings.voyage import VoyageEmbedder
from app.infrastructure.llm.groq_client import GroqClient
from app.infrastructure.reranker.cohere_client import CohereReranker
from app.infrastructure.retrieval.bm25 import BM25Retriever
from app.infrastructure.retrieval.rrf import rrf_merge
from app.infrastructure.retrieval.types import RetrievedChunk
from app.infrastructure.vector_store.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)

_SUMMARY_THRESHOLD = 10  # start summarizing once a conversation exceeds this many messages


class ChatService:
    def __init__(
        self,
        conv_repo: ConversationRepository,
        msg_repo: MessageRepository,
        embedder: VoyageEmbedder,
        pinecone: PineconeClient,
        bm25: BM25Retriever,
        reranker: CohereReranker,
        groq: GroqClient,
    ) -> None:
        self._conv_repo = conv_repo
        self._msg_repo = msg_repo
        self._embedder = embedder
        self._pinecone = pinecone
        self._bm25 = bm25
        self._reranker = reranker
        self._groq = groq

    async def chat(
        self,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        conversation_id: uuid.UUID | None = None,
    ) -> ChatResponse:
        t0 = time.monotonic()

        # 1. Daily message limit
        today_count = await self._msg_repo.count_today(user_id)
        if today_count >= MAX_CHAT_MESSAGES_PER_DAY:
            raise DailyLimitExceeded(
                f"Daily limit of {MAX_CHAT_MESSAGES_PER_DAY} messages reached — resets at midnight UTC"
            )

        # 2. Get or create conversation
        if conversation_id is not None:
            conv = await self._conv_repo.get(conversation_id, kb_id, user_id)
            if conv is None:
                raise ConversationNotFound(f"Conversation {conversation_id} not found")
        else:
            conv = await self._conv_repo.create(kb_id, user_id)

        # 3. Load summary + last 5 messages for context
        summary = conv.summary
        history = await self._msg_repo.get_last_n(conv.id, 5)

        # 4. Rewrite query if this is a follow-up
        rewritten_query = query
        rewrite_cost = 0.0
        if history:
            rewritten_query, rewrite_cost = await self._groq.rewrite_query(
                query, history, summary=summary
            )

        # 5. Embed query
        [query_vector] = await self._embedder.embed([rewritten_query])

        # 6. Parallel: dense + BM25 retrieval
        dense_chunks, bm25_chunks = await asyncio.gather(
            asyncio.to_thread(
                self._pinecone.query,
                kb_id=kb_id,
                user_id=user_id,
                vector=query_vector,
                top_k=20,
            ),
            self._bm25.query(kb_id=kb_id, query=rewritten_query, top_k=20),
        )

        # 7. RRF fusion
        fused = rrf_merge(dense_chunks, bm25_chunks, k=60, top_n=20)

        if not fused:
            answer = "I don't have enough information in the provided sources to answer that."
            citations: list[CitationItem] = []
            gen_cost = 0.0
        else:
            # 8. Cohere rerank (fall back to top-5 RRF if budget exceeded)
            try:
                top_chunks = await self._reranker.rerank(
                    rewritten_query, fused, top_n=5
                )
            except BudgetExceeded:
                logger.warning("Cohere budget exceeded — using top-5 RRF results")
                top_chunks = fused[:5]

            # 9. Generate
            answer, gen_cost = await self._groq.generate(
                query=rewritten_query,
                chunks=top_chunks,
                history=history,
                summary=summary,
            )

            # 10. Parse citations
            citations = parse_citations(answer, top_chunks)

        total_cost = rewrite_cost + gen_cost
        latency_ms = int((time.monotonic() - t0) * 1000)

        # 11. Persist user message + assistant message
        await self._msg_repo.create(conv.id, "user", query)
        await self._msg_repo.create(
            conv.id,
            "assistant",
            answer,
            citations=[c.model_dump() for c in citations],
            latency_ms=latency_ms,
            cost_usd=total_cost,
        )

        # 12. Lazily update conversation summary once history grows beyond last-5 window
        total_count = await self._msg_repo.count_by_conversation(conv.id)
        if total_count > _SUMMARY_THRESHOLD:
            await self._update_summary(conv.id, conv.summary)

        return ChatResponse(
            conversation_id=conv.id,
            answer=answer,
            citations=citations,
            latency_ms=latency_ms,
            cost_usd=total_cost,
        )

    async def chat_stream(
        self,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        conversation_id: uuid.UUID | None = None,
    ):
        """Run the full pipeline and yield SSE-formatted strings. Final yield is the done event."""
        t0 = time.monotonic()

        # 1. Daily limit
        today_count = await self._msg_repo.count_today(user_id)
        if today_count >= MAX_CHAT_MESSAGES_PER_DAY:
            yield StreamErrorEvent(
                detail=f"Daily limit of {MAX_CHAT_MESSAGES_PER_DAY} messages reached — resets at midnight UTC"
            ).model_dump_json()
            return

        # 2. Get or create conversation
        if conversation_id is not None:
            conv = await self._conv_repo.get(conversation_id, kb_id, user_id)
            if conv is None:
                yield StreamErrorEvent(detail=f"Conversation {conversation_id} not found").model_dump_json()
                return
        else:
            conv = await self._conv_repo.create(kb_id, user_id)

        # 3. Load summary + last 5 messages
        summary = conv.summary
        history = await self._msg_repo.get_last_n(conv.id, 5)

        # 4. Rewrite query if follow-up
        rewritten_query = query
        rewrite_cost = 0.0
        if history:
            rewritten_query, rewrite_cost = await self._groq.rewrite_query(
                query, history, summary=summary
            )

        # 5. Embed query
        [query_vector] = await self._embedder.embed([rewritten_query])

        # 6. Parallel retrieval
        dense_chunks, bm25_chunks = await asyncio.gather(
            asyncio.to_thread(
                self._pinecone.query,
                kb_id=kb_id,
                user_id=user_id,
                vector=query_vector,
                top_k=20,
            ),
            self._bm25.query(kb_id=kb_id, query=rewritten_query, top_k=20),
        )

        # 7. RRF fusion
        fused = rrf_merge(dense_chunks, bm25_chunks, k=60, top_n=20)

        if not fused:
            answer = "I don't have enough information in the provided sources to answer that."
            citations: list[CitationItem] = []
            gen_cost = 0.0
        else:
            # 8. Cohere rerank
            try:
                top_chunks = await self._reranker.rerank(rewritten_query, fused, top_n=5)
            except BudgetExceeded:
                logger.warning("Cohere budget exceeded — using top-5 RRF results")
                top_chunks = fused[:5]

            # 9. Stream generation — collect full answer while yielding tokens
            answer_parts: list[str] = []
            gen_cost = 0.0
            async for token, cost in self._groq.generate_stream(
                query=rewritten_query,
                chunks=top_chunks,
                history=history,
                summary=summary,
            ):
                if token is None:
                    gen_cost = cost
                else:
                    answer_parts.append(token)
                    yield StreamTokenEvent(content=token).model_dump_json()

            answer = "".join(answer_parts)
            citations = parse_citations(answer, top_chunks)

        total_cost = rewrite_cost + gen_cost
        latency_ms = int((time.monotonic() - t0) * 1000)

        # 10. Persist messages
        await self._msg_repo.create(conv.id, "user", query)
        await self._msg_repo.create(
            conv.id,
            "assistant",
            answer,
            citations=[c.model_dump() for c in citations],
            latency_ms=latency_ms,
            cost_usd=total_cost,
        )

        # 11. Lazily update summary
        total_count = await self._msg_repo.count_by_conversation(conv.id)
        if total_count > _SUMMARY_THRESHOLD:
            await self._update_summary(conv.id, conv.summary)

        yield StreamDoneEvent(
            conversation_id=conv.id,
            citations=citations,
            latency_ms=latency_ms,
            cost_usd=total_cost,
        ).model_dump_json()

    async def _update_summary(
        self, conversation_id: uuid.UUID, existing_summary: str | None
    ) -> None:
        old_messages = await self._msg_repo.get_all_except_last_n(conversation_id, 5)
        if not old_messages:
            return
        new_summary, _ = await self._groq.summarize_history(old_messages, existing_summary)
        await self._conv_repo.update_summary(conversation_id, new_summary)

    async def list_conversations(self, kb_id: uuid.UUID, user_id: uuid.UUID) -> list:
        return await self._conv_repo.list_by_kb(kb_id, user_id)

    async def get_messages(
        self, conversation_id: uuid.UUID, kb_id: uuid.UUID, user_id: uuid.UUID
    ) -> list:
        conv = await self._conv_repo.get(conversation_id, kb_id, user_id)
        if conv is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return await self._msg_repo.list_by_conversation(conversation_id)

