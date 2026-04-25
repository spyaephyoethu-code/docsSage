from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def run_migrations() -> None:
    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"
        )
        for sql_file in sql_files:
            row = await conn.fetchrow(
                "SELECT 1 FROM schema_migrations WHERE filename = $1",
                sql_file.name,
            )
            if row is None:
                await conn.execute(sql_file.read_text())
                await conn.execute(
                    "INSERT INTO schema_migrations(filename) VALUES ($1)",
                    sql_file.name,
                )
    finally:
        await conn.close()
