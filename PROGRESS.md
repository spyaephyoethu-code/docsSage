# DocsSage — Progress Log

## Last updated: 2026-04-21

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
