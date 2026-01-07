"""
QRSecure Analytics Routes
Handles analytics data retrieval for QR codes.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models import URL, User, Scan
from routes.auth import get_current_user, require_auth
from services.analytics import get_analytics_summary, get_scans_timeline

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/global/stats")
async def get_global_stats(db: AsyncSession = Depends(get_db)):
    """
    Get global platform statistics for landing page.
    Public endpoint - no auth required.
    """
    # Count total QR codes
    qr_count_result = await db.execute(select(func.count(URL.url_id)))
    total_qr_codes = qr_count_result.scalar() or 0
    
    # Sum total scans
    scans_result = await db.execute(select(func.sum(URL.total_scans)))
    total_scans = scans_result.scalar() or 0
    
    # Count unique countries
    countries_result = await db.execute(
        select(func.count(func.distinct(Scan.country)))
        .filter(Scan.country.isnot(None), Scan.country != "Unknown")
    )
    unique_countries = countries_result.scalar() or 0
    
    return {
        "qr_codes_created": total_qr_codes,
        "total_scans": total_scans,
        "unique_countries": unique_countries,
        "uptime_percent": 99.9  # Static for now, could be calculated from monitoring
    }


@router.get("/user/scans-today")
async def get_user_scans_today(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Get total scans today for the current user's QR codes.
    Uses US Pacific (Oregon) timezone for consistency with Render server.
    """
    import pytz
    
    # Use US Pacific timezone (Oregon where Render servers are)
    pacific = pytz.timezone('US/Pacific')
    now_pacific = datetime.now(pacific)
    today_start = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Convert to UTC for database query
    today_start_utc = today_start.astimezone(pytz.UTC).replace(tzinfo=None)
    
    # Get user's URL IDs
    urls_result = await db.execute(
        select(URL.url_id).filter(URL.user_id == user.user_id)
    )
    url_ids = [row[0] for row in urls_result.fetchall()]
    
    if not url_ids:
        return {"scans_today": 0}
    
    # Count scans today
    scans_result = await db.execute(
        select(func.count(Scan.scan_id))
        .filter(Scan.url_id.in_(url_ids), Scan.scanned_at >= today_start_utc)
    )
    scans_today = scans_result.scalar() or 0
    
    return {"scans_today": scans_today}


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
