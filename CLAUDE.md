# DocsSage — RAG Documentation Assistant

## What this is
A RAG-powered chatbot. Users create "knowledge bases" by ingesting docs (GitHub repos, PDFs, websites, Notion exports), then chat with them and get answers with inline citations.

## Stack
- **LLM:** Groq — two models: `llama-3.3-70b` for final generation (streaming via SSE, temperature 0.1), `llama-3.1-8b-instant` for query rewriting only
- **Embeddings:** Voyage AI (`voyage-3-lite`) — batch size 128, retry on 429
- **Vector DB:** Pinecone serverless — shared index, filter by `user_id` + `kb_id`
- **Sparse search:** BM25 in-process (`rank_bm25` library), rebuilt lazily per-KB on first query, chunks sourced from Supabase
- **Re-ranker:** Cohere `rerank-english-v3.0`
- **Orchestration:** LlamaIndex
- **Backend:** FastAPI (Python 3.11+) on Railway
- **Frontend:** Next.js 15 + Vercel AI SDK + shadcn/ui on Vercel
- **Database + Auth + Storage:** Supabase (Postgres + Supabase Auth + Supabase Storage)
- **Evaluation:** RAGAS + 50-question hand-curated eval set
- **Ingestion libraries:** `gitpython` (GitHub), `PyMuPDF/fitz` (PDF), `trafilatura` + `httpx` (web crawl)

## Key architectural decisions
- Single Pinecone index, metadata filtering by `user_id`/`kb_id` (not per-user namespaces) — cost reason
- Ingestion runs as FastAPI `BackgroundTasks` — user can close browser, job status persisted in Supabase (`pending` → `running` → `completed` / `failed`)
- `chunks_metadata` table in Postgres stores chunk text to serve citations without round-tripping Pinecone
- Chunking strategy is chosen by the developer per source type (not user-configurable): fixed-size (512 tokens, 50 overlap) as baseline, semantic (`SemanticSplitterNodeParser`) for prose, recursive markdown-aware (headers first, then paragraphs) for structured/API docs — strategy tracked per source in `sources` table for eval comparison
- BM25 index is in-memory (`rank_bm25`), rebuilt lazily per-KB on first query from `chunks_metadata`, RRF k=60
- Query rewriting: if conversational follow-up detected, rewrite standalone question using Groq (8B) + last 5 turns before retrieval
- BM25 snapshots persisted to Supabase Storage (not S3)
- Pinecone vector metadata schema: `{kb_id, source_id, source_type, chunk_text, page_num?, url?}`

## RAG pipeline (query time)
1. Rewrite query using conversation history if needed
2. Embed rewritten query (Voyage)
3. Parallel retrieval: Pinecone top-20 (dense) + BM25 top-20 (sparse)
4. Reciprocal Rank Fusion → top-20 unique
5. Cohere Rerank → top-5
6. Build prompt with chunks + citation format (`[1]`, `[2]`...)
7. Stream Groq response via SSE
8. Parse citations, persist message with latency + cost metadata

## Backend file layout

The backend follows a strict layered architecture. Data flows top-down only — `api` → `domain` → `infrastructure`. No layer imports from a layer above it.

```
backend/app/
├── api/                          # HTTP layer only
│   ├── controllers/              # parse request, call service, map domain exceptions → HTTP errors
│   ├── routers/                  # FastAPI route registration only — no logic
│   └── validators/               # FastAPI dependencies for request-level checks (file size, content-type, etc.)
│
├── domain/                       # Business logic — no HTTP, no DB imports
│   ├── exceptions.py             # KBNotFound, KBLimitExceeded, BudgetExceeded, …
│   ├── schemas/                  # Pydantic request/response models shared across layers
│   └── services/                 # Orchestration: quota enforcement, calling repositories
│
├── infrastructure/               # All external I/O — swappable without touching other layers
│   ├── db/
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   └── repositories/        # One repository class per domain entity (raw DB queries only)
│   ├── vector_store/             # Pinecone client (→ Qdrant swap here)
│   ├── llm/                      # Groq client (→ OpenAI swap here)
│   ├── embeddings/               # Voyage AI client
│   ├── reranker/                 # Cohere client (with no-rerank fallback)
│   ├── storage/                  # Supabase Storage (BM25 snapshots, PDFs)
│   └── cache/                    # Query / retrieval / embedding caches
│
└── core/                         # Cross-cutting — imported by all layers
    ├── config.py                 # pydantic-settings (reads .env)
    ├── database.py               # async SQLAlchemy engine + session + migrations runner
    ├── quotas.py                 # quota constants read from settings
    ├── circuit_breaker.py        # daily budget guards for Groq / Voyage / Cohere
    └── middleware/
        └── auth.py               # JWT decode + get_current_user dependency
```


## Data model (Postgres)
- `users`, `knowledge_bases`, `sources`, `chunks_metadata`, `conversations`, `messages`, `eval_runs`
- `messages` stores `citations` (JSONB), `latency_ms`, `cost_usd` for eval and observability

## Free-tier constraints (this is a portfolio project — no paid spend)

### Per-user hard limits (enforce in `core/quotas.py`)
- Max 3 KBs per user
- Max 5 sources per KB
- Max 10MB per PDF upload
- Max 50 pages per website crawl
- Max 1 GitHub repo per ingest, repos under 100MB only
- Max 5,000 chunks per KB
- Max 20 chat messages per user per day
- Max 5 ingestions per user per day

### Global circuit breakers (enforce in `core/circuit_breaker.py`)
- Daily Groq token budget — when hit, return friendly "service paused" message
- Daily Voyage token budget — pause new ingestions
- Daily Cohere call budget — fall back to no-rerank mode automatically (do not error)

### Cost-saving decisions that affect code
- Use Llama 3.1 8B (not 70B) for query rewriting — save 70B for final generation only
- Cap generation response at 500 tokens
- Cache query results: hash of `(kb_id, normalized_query)` → cached answer 24h
- Cache retrieval results: same hash → cached top-5 chunks for 1h (saves Pinecone reads)
- Cache embeddings by content hash — store hash → vector in Postgres, skip re-embedding duplicates
- Dedupe chunks within a source before embedding (exact match)
- Skip chunks under 50 tokens

### Explicitly cut features — do not implement these
- Multi-turn conversation memory beyond last 5 messages
- Re-embedding when chunking strategy changes
- KB sharing between users
- Webhooks for ingestion completion — use polling every 2s instead
- Streaming ingestion progress — poll every 2s instead
- Auto-refresh of website sources (one-shot ingest only)
- **Clerk** — skipped entirely; Supabase Auth covers all auth needs (email/password, OAuth, JWTs, RLS) without a second vendor or extra cost

## Code conventions

### Import separation
Split imports into two labelled blocks everywhere — runtime imports first, type-hint imports second:
```python
# runtime imports
from app.core.dependencies import get_kb_service
from app.domain.exceptions import KBNotFound

# type-hint imports
from app.domain.services.kb_service import KBService
from app.infrastructure.db.models import KnowledgeBase
```
- **Runtime:** anything the function/class body actually calls, instantiates, or raises
- **Type-hint:** classes used only as annotations; never constructed in this file

## Frontend to-do: surface limits to users

Show limits inline so users understand constraints before hitting a 429 error.

### KB list page
- Show "X / 3 knowledge bases used" near the "Create KB" button
- Disable the button and show a tooltip ("You've reached the 3 KB limit") when at limit

### Source list page (inside a KB)
- Show "X / 5 sources" near the "Add Source" button
- Disable the button with tooltip when at limit
- Show ingestion status badge per source: `pending` (spinner) → `running` (spinner) → `completed` (green) / `failed` (red)
- Poll `GET /kbs/{kb_id}/sources/{source_id}` every 2s while status is `pending` or `running`; stop polling on `completed` or `failed`
- On `failed`: show a retry affordance (re-POST the same source)

### Add Source form
- Web: note "up to 50 pages crawled"
- GitHub: note "repos under 100MB only"
- PDF: note "max 10MB"

### Chat page
- Show "X / 20 messages today" somewhere visible (e.g., input footer)
- Disable input and show "Daily limit reached — resets at midnight UTC" when at 20

### General
- Map 429 responses from the API to user-friendly inline messages, not browser alerts
- Map circuit-breaker 503 responses ("service paused") to a banner at the top of the page

## Setup decisions log (Phase 0)
- **Auth:** Supabase Auth only — Clerk was listed in original plan but dropped; no Clerk account, no Clerk SDK
- **Pinecone index config:** dimension `512` (voyage-3-lite), metric `cosine`, serverless region `us-east-1-aws`
- **CI:** ruff (lint + format) + mypy for backend; ESLint + tsc for frontend — runs on push to `main`/`dev` and on PRs to `main`
