# DocsSage — Progress Log

## Last updated: 2026-04-22

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

## Phase 2 — Ingestion pipeline (IN PROGRESS)

### What was done
- **4 loaders:** GitHub (gitpython, depth=1 clone), PDF (PyMuPDF page-by-page), Web (trafilatura + httpx crawler up to 50 pages), plain Text, Word (.docx via python-docx)
- **3 chunkers:** Fixed (512 tokens, 50 overlap via tiktoken), Markdown (header-first recursive), Semantic (sentence-boundary grouping by paragraph)
- Chunking strategy auto-selected per source type — not user-configurable (github→markdown, pdf→fixed, web→semantic, text→fixed, word→semantic)
- **Voyage embedder:** httpx-based, batches of 128, exponential backoff retry on 429
- **Pinecone client:** upsert with metadata (kb_id, source_id, user_id, chunk_text), delete by source
- **Sources API:** `POST /api/v1/knowledge-bases/{kb_id}/sources` (202, triggers BackgroundTask), `GET .../sources`, `GET .../sources/{id}` (poll status)
- Ingestion status lifecycle: `pending → running → completed / failed`
- Deduplication: exact-match within a source before embedding; chunks under 50 tokens dropped
- Migration `008` adds `chunking_strategy` column to `sources` table

### Source type decision
Notion was dropped in favour of plain text and Word (.docx):
- Notion requires users to export a ZIP and host it somewhere — too many steps for a portfolio project
- Plain text and Word cover far more real-world documentation (specs, runbooks, internal docs)
- Excel was considered but skipped — tabular data doesn't chunk into meaningful prose for RAG

### Outstanding
- Install new deps: `pip install -r requirements.txt`
- End-to-end test: POST a GitHub URL → poll until `completed` → verify chunk count in logs

---

### Outstanding before Railway deploy
- Fill in `SUPABASE_JWT_SECRET` in `backend/.env` — get from Supabase Dashboard → Settings → API → JWT Secret
- Run `migrations/001_initial_schema.sql` in Supabase SQL editor once (the trigger on `auth.users` must be created there, not via asyncpg)
- Push to Railway and confirm `/health` returns 200
