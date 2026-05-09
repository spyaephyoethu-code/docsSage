import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# runtime imports
from app.core.config import settings
from app.core.database import AsyncSessionLocal, run_migrations
from app.infrastructure.db.repositories.source_repository import SourceRepository
from app.api.routers import chat, health, knowledge_bases, sources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await run_migrations()
    async with AsyncSessionLocal() as db:
        count = await SourceRepository(db).reset_stale_running()
        if count:
            logger.warning(
                f"Reset {count} stale 'running' source(s) to 'failed' on startup"
            )
    yield


app = FastAPI(title="DocsSage API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(knowledge_bases.router)
app.include_router(sources.router)
app.include_router(chat.router)
