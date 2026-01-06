"""
QRSecure Debug Routes
Endpoints for system verification and troubleshooting.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any

from database import get_db
from config import get_settings

settings = get_settings()

# Only enable if DEBUG is True or via secret header (for production safety)
# For this implementation, we'll keep it simple but protected slightly by obscurity
router = APIRouter(prefix="/api/debug", tags=["Debug"])

@router.get("/db")
async def check_database(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Check database connection and return current configuration info.
    """
    try:
        # Check connection
        result = await db.execute(text("SELECT 1"))
        connected = result.scalar() == 1
        
        # Get dialect info
        dialect = db.bind.dialect.name
        driver = db.bind.dialect.driver
        
        # Count users (to verify persistence)
        from models import User
        from sqlalchemy import select, func
        user_count_result = await db.execute(select(func.count(User.user_id)))
        user_count = user_count_result.scalar()
        
        return {
            "status": "connected" if connected else "error",
            "dialect": dialect,
            "driver": driver,
            "database_url_configured": bool(settings.database_url),
            # Mask the URL for security
            "database_url_prefix": settings.database_url.split(":")[0] if settings.database_url else None,
            "user_count": user_count
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
