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
    user: User = Depends(require_auth),
    tz_offset: int = 0  # Client timezone offset in minutes (e.g., IST = -330)
):
    """
    Get total scans today for the current user's QR codes.
    Uses UTC midnight by default, can accept client timezone offset.
    
    Args:
        tz_offset: Client timezone offset in minutes from UTC (negative for ahead of UTC)
                   Example: IST (UTC+5:30) would be -330
    """
    from datetime import timezone as dt_timezone
    
    # Calculate today's start in UTC
    now_utc = datetime.now(dt_timezone.utc)
    
    # If client provides timezone offset, adjust the "today" calculation
    if tz_offset != 0:
        # Client offset in hours
        offset_hours = -tz_offset / 60  # Negative because JS returns negative for ahead
        client_now = now_utc + timedelta(hours=offset_hours)
        today_start = client_now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert back to UTC for query
        today_start_utc = today_start - timedelta(hours=offset_hours)
    else:
        # Default: use UTC midnight
        today_start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Remove timezone info for database query
    today_start_utc = today_start_utc.replace(tzinfo=None)
    
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
