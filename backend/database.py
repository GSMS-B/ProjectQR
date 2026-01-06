"""
QRSecure Database Module
Production-grade database connection handling for SQLite (local) and PostgreSQL (Supabase/Render).
"""

import os
import ssl
from urllib.parse import urlparse, parse_qs, unquote

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from config import get_settings

# Get settings
settings = get_settings()


def prepare_database_url(raw_url: str) -> tuple[str, dict]:
    """
    Parse and prepare the database URL for SQLAlchemy asyncpg.
    
    Returns:
        tuple: (processed_url, connect_args)
    """
    if not raw_url:
        raise ValueError("DATABASE_URL is not set")
    
    connect_args = {}
    
    # SQLite: no changes needed
    if raw_url.startswith("sqlite"):
        return raw_url, connect_args
    
    # PostgreSQL: needs driver prefix and SSL configuration
    parsed = urlparse(raw_url)
    
    # Determine the scheme
    scheme = parsed.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+asyncpg":
        pass  # Already correct
    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")
    
    # Extract credentials (handle URL-encoded passwords)
    username = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname or ""
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") if parsed.path else "postgres"
    
    # Log connection info (masked) for debugging
    masked_password = "***" if password else "(empty)"
    print(f"🔌 Database connection:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Database: {database}")
    print(f"   Username: {username}")
    print(f"   Password: {masked_password}")
    
    # Detect if using Supabase connection pooler
    is_supabase_pooler = "pooler.supabase.com" in host
    is_supabase_direct = "supabase.co" in host or "supabase.com" in host
    
    if is_supabase_pooler:
        print(f"   Mode: Supabase Connection Pooler (Session Mode)")
        # Connection pooler requires NullPool and no prepared statements
        connect_args["prepared_statement_cache_size"] = 0
        # SSL is REQUIRED for Supabase
        connect_args["ssl"] = True
    elif is_supabase_direct:
        print(f"   Mode: Supabase Direct Connection")
        connect_args["ssl"] = True
    else:
        # Generic PostgreSQL - try SSL but don't require it
        print(f"   Mode: Generic PostgreSQL")
        # For other hosts, we can try SSL prefer mode
        # asyncpg uses ssl=True for sslmode=require
        connect_args["ssl"] = "prefer"
    
    # Reconstruct the URL with the correct scheme
    # We need to properly encode special characters in password
    from urllib.parse import quote
    encoded_password = quote(password, safe="")
    
    processed_url = f"{scheme}://{username}:{encoded_password}@{host}:{port}/{database}"
    
    # Preserve query parameters (except sslmode which we handle via connect_args)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        # Remove sslmode as we handle it via connect_args
        query_params.pop("sslmode", None)
        if query_params:
            query_string = "&".join(f"{k}={v[0]}" for k, v in query_params.items())
            processed_url = f"{processed_url}?{query_string}"
    
    return processed_url, connect_args


# Prepare the database URL
database_url, connect_args = prepare_database_url(settings.database_url)

# Determine if we should use NullPool (required for external connection poolers)
is_using_pooler = "pooler.supabase.com" in settings.database_url if settings.database_url else False

# Build engine kwargs
engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}

if connect_args:
    engine_kwargs["connect_args"] = connect_args

if is_using_pooler:
    # Use NullPool when external pooler handles connection management
    engine_kwargs["poolclass"] = NullPool
    print("   Pooling: Disabled (using external pooler)")
else:
    print("   Pooling: SQLAlchemy default")

# Create async engine
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
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        # Re-raise to prevent app from starting with broken DB
        raise


async def check_db_connection() -> dict:
    """
    Test database connectivity.
    Returns a status dict for health checks.
    """
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                return {"status": "connected", "message": "Database is reachable"}
    except Exception as e:
        return {"status": "error", "message": str(e), "error_type": type(e).__name__}
    
    return {"status": "unknown", "message": "Unexpected state"}


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
