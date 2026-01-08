"""
QRSecure Database Module
Production-grade database connection handling for SQLite (local) and PostgreSQL (Supabase/Render).
"""

import os
import re
from urllib.parse import quote

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
    
    This function uses regex-based parsing instead of urlparse to avoid issues
    with special characters in passwords (like brackets).
    
    Returns:
        tuple: (processed_url, connect_args)
    """
    if not raw_url:
        raise ValueError("DATABASE_URL is not set")
    
    connect_args = {}
    
    # SQLite: no changes needed
    if raw_url.startswith("sqlite"):
        print(f"🔌 Database: SQLite (local development)")
        return raw_url, connect_args
    
    # PostgreSQL URL pattern: scheme://user:password@host:port/database
    # Using regex to handle special characters in password
    pattern = r'^(postgres(?:ql)?(?:\+asyncpg)?):\/\/([^:]+):(.+)@([^:]+):(\d+)\/(.+?)(?:\?.*)?$'
    match = re.match(pattern, raw_url)
    
    if not match:
        # Try simpler pattern without password
        pattern_no_pass = r'^(postgres(?:ql)?(?:\+asyncpg)?):\/\/([^@]+)@([^:]+):(\d+)\/(.+?)(?:\?.*)?$'
        match_no_pass = re.match(pattern_no_pass, raw_url)
        if match_no_pass:
            raise ValueError("DATABASE_URL appears to be missing a password")
        raise ValueError(f"Invalid DATABASE_URL format. Expected: postgresql://user:password@host:port/database")
    
    scheme, username, password, host, port, database = match.groups()
    port = int(port)
    
    # Log connection info (masked) for debugging
    masked_password = "***" if password else "(empty)"
    print(f"🔌 Database connection:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Database: {database}")
    print(f"   Username: {username}")
    print(f"   Password: {masked_password} (length: {len(password)})")
    
    # Detect Supabase
    is_supabase_pooler = "pooler.supabase.com" in host
    is_supabase_direct = "supabase.co" in host
    
    # Detect Render PostgreSQL (uses pgbouncer)
    is_render = "render.com" in host or "oregon-postgres.render.com" in host
    
    # Detect Neon (also uses pgbouncer)
    is_neon = "neon.tech" in host
    
    # Any provider using pgbouncer needs statement cache disabled
    uses_pgbouncer = is_supabase_pooler or is_render or is_neon
    
    if uses_pgbouncer:
        # Connection pooler requires statement cache disabled
        connect_args["prepared_statement_cache_size"] = 0
        print(f"   ⚠️ PgBouncer detected - statement cache disabled")
    
    if is_supabase_pooler:
        if port == 6543:
            print(f"   Mode: Supabase Transaction Pooler (port 6543)")
        elif port == 5432:
            print(f"   Mode: Supabase Session Pooler (port 5432)")
        else:
            print(f"   Mode: Supabase Pooler (unknown port {port})")
        
        # SSL is REQUIRED for Supabase, but we need to skip certificate verification
        # because the pooler uses certificates not in standard trust stores
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context
        print(f"   SSL: Enabled (no cert verification)")
        
    elif is_supabase_direct:
        print(f"   Mode: Supabase Direct Connection")
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context
        
    elif is_render:
        print(f"   Mode: Render PostgreSQL")
        # Render uses internal SSL but may not need explicit config
        
    elif is_neon:
        print(f"   Mode: Neon PostgreSQL")
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context
        
    else:
        print(f"   Mode: Generic PostgreSQL")
    
    # URL-encode the password to handle special characters like [], @, #, etc.
    encoded_password = quote(password, safe="")
    
    # Build the URL with asyncpg driver
    processed_url = f"postgresql+asyncpg://{username}:{encoded_password}@{host}:{port}/{database}"
    
    print(f"   Pooling: {'Disabled (external pooler)' if is_supabase_pooler else 'SQLAlchemy default'}")
    
    return processed_url, connect_args


# Prepare the database URL
try:
    database_url, connect_args = prepare_database_url(settings.database_url)
except Exception as e:
    print(f"❌ Error parsing DATABASE_URL: {e}")
    print(f"   Raw URL starts with: {settings.database_url[:30] if settings.database_url else '(empty)'}...")
    raise

# Determine if we should use NullPool (required for external connection poolers)
is_using_pooler = any(x in settings.database_url for x in ["pooler.supabase.com", "render.com", "neon.tech"]) if settings.database_url else False

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
