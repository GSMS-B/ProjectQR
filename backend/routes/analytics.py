"""
QRSecure Analytics Routes
Handles analytics data retrieval for QR codes.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import URL, User
from routes.auth import get_current_user, require_auth
from services.analytics import get_analytics_summary, get_scans_timeline

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/{short_code}")
async def get_analytics(
    short_code: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Get comprehensive analytics for a QR code.
    """
    # Validate days parameter
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
    
    # Find URL and verify ownership
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Get analytics
    analytics = await get_analytics_summary(db, url.url_id, days)
    
    return {
        "short_code": short_code,
        "destination": url.original_url,
        "period_days": days,
        **analytics
    }


@router.get("/{short_code}/timeline")
async def get_timeline(
    short_code: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Get scans timeline for charting.
    """
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
    
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    timeline = await get_scans_timeline(db, url.url_id, days)
    
    return {
        "short_code": short_code,
        "period_days": days,
        "timeline": timeline
    }


@router.get("/{short_code}/summary")
async def get_quick_summary(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Get quick summary stats for dashboard display.
    """
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Get 7-day analytics
    analytics = await get_analytics_summary(db, url.url_id, days=7)
    
    return {
        "short_code": short_code,
        "total_scans": url.total_scans,
        "scans_last_7_days": analytics["total_scans"],
        "scans_today": analytics["scans_today"],
        "top_country": analytics["top_countries"][0] if analytics["top_countries"] else None,
        "top_device": max(analytics["devices"].items(), key=lambda x: x[1])[0] if analytics["devices"] else None
    }
