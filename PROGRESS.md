# DocsSage — Progress Log

## Last updated: 2026-05-09 (Phase 4 done)

---

## Phase 0 — Setup (COMPLETED)

### What was done
- GitHub repo created (monorepo: `frontend/`, `backend/`)
- Monorepo directory structure created (`frontend/`, `backend/`, `.github/workflows/`)
- `.env.example` written for root, `backend/`, and `frontend/`
- `.env` created locally (all keys filled in)
- `SECRET_KEY` generated and saved
- `.gitignore` created — `.env` excluded
- CI workflow created at `.github/workflows/ci.yml`
  - Backend: ruff (lint + format check) + mypy on Python 3.11
  - Frontend: ESLint + tsc on Node 20
  - Triggers: push to `main`/`dev`, PR to `main`
- All service accounts provisioned: Supabase, Groq, Voyage AI, Pinecone, Cohere, Vercel, Railway
- Pinecone index `docssage` created (dim=512, cosine, serverless us-east-1-aws)
- Auth decision: Supabase Auth only — Clerk dropped
- `CLAUDE.md` updated to reflect Clerk decision + Pinecone config

---

## Phase 1 — Backend skeleton (COMPLETED)

### What was done
- `backend/` venv created at `backend/.venv`; `requirements.txt` pinned
- `pyproject.toml` — ruff (E/F/I/UP, line-length 88) + mypy (pydantic plugin) config
- `app/config.py` — `pydantic-settings` `Settings`; `async_database_url` and `cors_origins` properties
- `app/database.py` — SQLAlchemy 2.0 async engine + `get_db` dependency + `run_migrations()` (idempotent, tracked in `schema_migrations` table)
- `app/models/__init__.py` — all ORM models: `User`, `KnowledgeBase`, `Source`, `ChunkMetadata`, `Conversation`, `Message`, `EvalRun`
- `app/middleware/auth.py` — `get_current_user` FastAPI dependency: HS256 JWT decode via PyJWT + upsert user into `public.users`
- `app/schemas/kb.py` — `KBCreate`, `KBUpdate`, `KBResponse` Pydantic schemas
- `app/routers/health.py` — `GET /health` returns `{"status": "ok"}`
- `app/routers/knowledge_bases.py` — full KB CRUD (`GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`) with quota check (max 3 per user)
- `app/main.py` — FastAPI app with lifespan (runs migrations on start), CORS, routers
- `migrations/001_initial_schema.sql` — all tables + indexes + `handle_new_user` trigger to mirror `auth.users` → `public.users`
- `Dockerfile` — Python 3.11-slim, uses `$PORT` env var
- `railway.toml` — Dockerfile builder, `/health` healthcheck
- `backend/.env` created (local copy with real keys); `SUPABASE_JWT_SECRET` added to `.env.example` and `.env`
- ruff: all checks pass; mypy: no issues (12 source files)

---

## Phase 2 — Ingestion pipeline (COMPLETED)

### What was done
- **5 loaders** (`infrastructure/ingestion/loaders/`): GitHub (gitpython, depth=1 clone), PDF (PyMuPDF page-by-page), Web (trafilatura + httpx crawler, up to 50 pages), plain Text, Word (.docx via python-docx) — all with shared `BaseLoader` ABC
- **3 chunkers** (`infrastructure/ingestion/chunkers/`): Fixed (512 tokens, 50 overlap via tiktoken), Markdown (header-first recursive), Semantic (sentence-boundary paragraph grouping) — all with shared `BaseChunker` ABC
- Chunking strategy auto-selected per source type, not user-configurable: github→markdown, pdf→fixed, web→semantic, text→fixed, word→semantic
- **Ingestion pipeline** (`infrastructure/ingestion/pipeline.py`): orchestrates load → chunk → dedupe → embed → upsert; deduplication is exact-match within a source; chunks under 50 tokens dropped
- **Voyage embedder** (`infrastructure/embeddings/voyage.py`): httpx-based, batch size 128, exponential backoff retry on 429
- **Pinecone client** (`infrastructure/vector_store/pinecone_client.py`): upsert with metadata (`kb_id`, `source_id`, `user_id`, `chunk_text`), delete-by-source support
- **Chunk repository** (`infrastructure/db/repositories/chunk_repository.py`): bulk-insert `chunks_metadata` rows after upsert
- **Source repository** (`infrastructure/db/repositories/source_repository.py`): status lifecycle writes (`pending → running → completed / failed`)
- **Source service** (`domain/services/source_service.py`): quota enforcement (max 5 sources per KB, max 5 ingestions/day), triggers `BackgroundTask` with pipeline
- **Sources API** (`api/routers/sources.py` + `api/controllers/source_controller.py`): `POST /api/v1/knowledge-bases/{kb_id}/sources` (202), `GET .../sources`, `GET .../sources/{id}` (for polling)
- **Migration `008`**: adds `chunking_strategy` column to `sources` table
- **Dependencies added** to `requirements.txt`: `gitpython`, `PyMuPDF`, `trafilatura`, `python-docx`, `tiktoken`, `pinecone-client`, `voyageai`

### Source type decision
Notion was dropped in favour of plain text and Word (.docx):
- Notion requires users to export a ZIP and host it somewhere — too many steps for a portfolio project
- Plain text and Word cover far more real-world documentation (specs, runbooks, internal docs)
- Excel was skipped — tabular data doesn't chunk into meaningful prose for RAG

---

---

## Phase 3 — Retrieval + Generation (COMPLETED)

### What was done
- **Dense retrieval** (`infrastructure/vector_store/pinecone_client.py`): `query()` method — top-20 via Pinecone, filtered by `kb_id` + `user_id`, returns `list[RetrievedChunk]`
- **BM25 retrieval** (`infrastructure/retrieval/bm25.py`): lazy per-KB index using `rank_bm25`; built on first query; build time logged (measured against full chunk set); cache invalidated automatically after each ingestion completes
- **RRF fusion** (`infrastructure/retrieval/rrf.py`): reciprocal rank fusion (k=60) over dense + sparse lists, deduplicates by `pinecone_id`, returns top-20
- **Cohere reranker** (`infrastructure/reranker/cohere_client.py`): `rerank-english-v3.0`, top-20 → top-5; silently falls back to top-5 RRF if daily Cohere budget is exceeded
- **Groq client** (`infrastructure/llm/groq_client.py`): httpx-based; `llama-3.3-70b-versatile` for generation (max 500 tokens, temperature 0.1); `llama-3.1-8b-instant` for query rewriting; returns `(answer, cost_usd)` tuple
- **Query rewriting**: triggered when conversation history exists (≥1 prior message); uses last 5 turns; Groq 8B standalone-question rewrite
- **Circuit breakers** (`core/circuit_breaker.py`): in-memory daily counters (process-local, resets at midnight); Groq (500k tokens), Voyage (10M tokens), Cohere (500 calls)
- **Conversation repository** (`infrastructure/db/repositories/conversation_repository.py`): create, get (ownership-checked), list-by-KB
- **Message repository** (`infrastructure/db/repositories/message_repository.py`): create, get-last-N, list-by-conversation, count-today (for daily limit)
- **Chat service** (`domain/services/chat_service.py`): full pipeline — daily limit check → get/create conversation → load history → rewrite → embed → dense+BM25 (parallel) → RRF → Cohere rerank → Groq generate → parse citations → persist messages → return response
- **Chat API** (`api/routers/chat.py` + `api/controllers/chat_controller.py`):
  - `POST /api/v1/knowledge-bases/{kb_id}/chat` → `ChatResponse` (conversation_id, answer, citations, latency_ms, cost_usd)
  - `GET /api/v1/knowledge-bases/{kb_id}/conversations`
  - `GET /api/v1/knowledge-bases/{kb_id}/conversations/{id}/messages`
- **Citation parsing**: regex `\[(\d+)\]` scans answer; only cited chunk indices returned in response
- `rank-bm25==0.2.2` added to `requirements.txt`
- mypy: 0 errors (70 source files); ruff: all checks pass

### Test via curl (non-streaming)
```bash
# 1. POST a chat message (new conversation)
curl -X POST http://localhost:8000/api/v1/knowledge-bases/{kb_id}/chat \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query": "How does authentication work?"}'

# 2. Continue the conversation
curl -X POST http://localhost:8000/api/v1/knowledge-bases/{kb_id}/chat \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What about OAuth?", "conversation_id": "<uuid from step 1>"}'
```

---

---

## Phase 3 improvements — Conversation Memory + Citation Names (2026-05-02)

### Conversation history: summary + last 5 messages

**Problem:** `get_last_n` was silently fetching the *oldest* N messages (`.asc().limit(n)`) instead of the most recent N. Also, raw history passed to the LLM grows unbounded as conversations get longer.

**What was done:**
- `migrations/005_create_conversations.sql`: added `summary TEXT` column to `conversations` table
- `infrastructure/db/models.py`: added `summary: Mapped[str | None]` to `Conversation` ORM model
- `infrastructure/db/repositories/message_repository.py`:
  - Fixed `get_last_n` to return the N *most recent* messages in ascending order (`.desc().limit(n)` + Python `reversed()`)
  - Added `count_by_conversation(conversation_id)` — total message count for a conversation
  - Added `get_all_except_last_n(conversation_id, n)` — all messages older than the last N (used for summarization input)
- `infrastructure/db/repositories/conversation_repository.py`: added `update_summary(conversation_id, summary)` — persists the new summary text
- `infrastructure/llm/groq_client.py`:
  - `rewrite_query()`: now accepts `summary=` kwarg; prepends it as "Conversation summary" before recent turns when present
  - `generate()`: same — summary shown first, then last 5 messages, then question
  - New `summarize_history(messages, existing_summary)`: 8B model, 300 token cap; does a fresh summary or incremental update depending on whether a prior summary exists
- `domain/services/chat_service.py`:
  - Step 3: loads `conv.summary` alongside `get_last_n(5)`
  - Both `rewrite_query` and `generate` receive `summary=`
  - Step 12 (new): after saving messages, if `total_count > _SUMMARY_THRESHOLD` (10), calls `_update_summary` which feeds all messages except last 5 to `summarize_history` and writes the result back to `conversations.summary`

**Context passed to LLM:** `summary (if exists) + last 5 messages`. All messages stay in DB untouched — summary is a cached digest only.

### Citation source names

**Problem:** `CitationItem` had no document name field. For PDF/Word/Text sources `source_url` is `None`, leaving citations with no human-readable source label. Also `source_title` in `chunks_metadata` was always `None` for these types because the pipeline used `c.metadata.get("file_path")` which only the GitHub loader sets.

**What was done:**
- `infrastructure/retrieval/types.py`: added `source_title: str | None = None` to `RetrievedChunk`
- `domain/schemas/chat.py`: added `source_name: str | None = None` to `CitationItem`
- `infrastructure/ingestion/pipeline.py`:
  - Derives `source_filename = os.path.basename(source.url_or_path)` as a per-source fallback name
  - Per chunk: uses `c.metadata.get("file_path") or source_filename` — GitHub chunks keep their per-file relative path (e.g. `src/api/routes.py`); PDF/Word/Text chunks get the filename (e.g. `manual.pdf`)
  - Injects `source_title` into both the Pinecone metadata dicts and the `bulk_create` rows
- `infrastructure/vector_store/pinecone_client.py`: stores `source_title` in Pinecone vector metadata on upsert; reads it back into `RetrievedChunk.source_title` on query
- `infrastructure/retrieval/bm25.py`: includes `source_title` in the in-memory metas dict during `_build`; maps it to `RetrievedChunk.source_title` in `_search`
- `domain/services/chat_service.py` `_parse_citations`: maps `chunk.source_title` → `CitationItem.source_name`

**Per source type result:**

| Source | `source_name` | `source_url` |
|---|---|---|
| GitHub | `src/api/routes.py` (per-file path) | full GitHub blob URL |
| PDF | `manual.pdf` | `null` |
| Word | `notes.docx` | `null` |
| Text | `readme.txt` | `null` |
| Web | `null` | full crawled URL |

---

---

## Phase 4 — SSE Streaming (COMPLETED)

### What was done
- **`groq_client.generate_stream()`** (`infrastructure/llm/groq_client.py`): httpx streaming request with `"stream": True` + `"stream_options": {"include_usage": True}`; parses SSE lines from Groq, yields `(token, 0.0)` per chunk and `(None, cost)` as the final item when usage arrives
- **`chat_service.chat_stream()`** (`domain/services/chat_service.py`): runs the identical pipeline as `chat()` (limit check → conversation → history → rewrite → embed → retrieve → RRF → rerank), then calls `generate_stream()` — yields `StreamTokenEvent` JSON strings while collecting the full answer, then persists messages and yields a final `StreamDoneEvent`
- **SSE event schema** (`domain/schemas/chat.py`): three event types added:
  - `StreamTokenEvent` — `{"type": "token", "content": "..."}` — one per streamed token
  - `StreamDoneEvent` — `{"type": "done", "conversation_id": "...", "citations": [...], "latency_ms": ..., "cost_usd": ...}` — sent once after persistence
  - `StreamErrorEvent` — `{"type": "error", "detail": "..."}` — daily limit or not-found errors
- **`POST /api/v1/knowledge-bases/{kb_id}/chat/stream`** (`api/routers/chat.py` + `api/controllers/chat_controller.py`): returns `StreamingResponse(media_type="text/event-stream")`; wraps the async generator from `chat_stream()` into `data: <json>\n\n` SSE frames

### Test via curl
```bash
curl -N -X POST http://localhost:8000/api/v1/knowledge-bases/{kb_id}/chat/stream \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"query": "How does authentication work?"}'
```

---

### Outstanding before Railway deploy
- Fill in `SUPABASE_JWT_SECRET` in `backend/.env` — get from Supabase Dashboard → Settings → API → JWT Secret
- Run `migrations/001_initial_schema.sql` in Supabase SQL editor once (the trigger on `auth.users` must be created there, not via asyncpg)
- Push to Railway and confirm `/health` returns 200
