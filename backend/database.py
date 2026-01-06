"""
QRSecure Database Module
Handles database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from config import get_settings

# Get settings
settings = get_settings()

# Fix database URL for Render/PostgreSQL
# Render provides postgres:// or postgresql:// but we need postgresql+asyncpg://
database_url = settings.database_url
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Determine if using connection pooler (Supabase pooler uses port 5432 or 6543 with pooler subdomain)
is_using_pooler = "pooler.supabase.com" in database_url if database_url else False

# Create async engine with appropriate settings
# When using Supabase's connection pooler, we need to disable prepared statements
# to avoid compatibility issues with PgBouncer/Supavisor
from sqlalchemy.pool import NullPool

engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}

if is_using_pooler:
    # Disable prepared statement cache for connection pooler compatibility
    engine_kwargs["connect_args"] = {"prepared_statement_cache_size": 0}
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(database_url, **engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    Usage in FastAPI:
        @app.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database session.
    Usage:
        async with get_db_context() as db:
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
