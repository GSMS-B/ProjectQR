"""
QRSecure Analytics Service
Handles scan logging and analytics aggregation.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models import Scan, URL
from services.geolocation import get_location_from_ip
from user_agents import parse as parse_user_agent


async def log_scan(
    db: AsyncSession,
    url_id: str,
    ip_address: str,
    user_agent: str,
    referrer: Optional[str] = None
) -> Scan:
    """
    Log a QR code scan with device and location information.
    
    Args:
        db: Database session
        url_id: UUID of the scanned URL
        ip_address: Client IP address
        user_agent: Browser user agent string
        referrer: HTTP referrer if available
    
    Returns:
        Created Scan record
    """
    # Parse user agent
    ua = None
    device_type = "Unknown"
    os_name = "Unknown"
    browser_name = "Unknown"
    
    if user_agent:
        try:
            ua = parse_user_agent(user_agent)
            
            # Determine device type
            if ua.is_mobile:
                device_type = "Mobile"
            elif ua.is_tablet:
                device_type = "Tablet"
            elif ua.is_pc:
                device_type = "Desktop"
            elif ua.is_bot:
                device_type = "Bot"
            else:
                device_type = ua.device.family or "Unknown"
            
            # Get OS and browser
            os_name = f"{ua.os.family}"
            if ua.os.version_string:
                os_name += f" {ua.os.version_string}"
            
            browser_name = f"{ua.browser.family}"
            if ua.browser.version_string:
                browser_name += f" {ua.browser.version_string}"
        except Exception:
            pass
    
    # Get location from IP
    location = get_location_from_ip(ip_address)
    
    # Create scan record
    scan = Scan(
        url_id=url_id,
        scanned_at=datetime.utcnow(),
        ip_address=ip_address,
        country=location.get("country"),
        country_code=location.get("country_code"),
        city=location.get("city"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        device_type=device_type,
        os=os_name,
        browser=browser_name,
        user_agent=user_agent,
        referrer=referrer
    )
    
    db.add(scan)
    
    # Increment total scans on URL
    url_result = await db.execute(select(URL).filter(URL.url_id == url_id))
    url = url_result.scalar_one_or_none()
    if url:
        url.total_scans += 1
    
    await db.commit()
    
    return scan


async def get_analytics_summary(
    db: AsyncSession,
    url_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get comprehensive analytics summary for a QR code.
    
    Args:
        db: Database session
        url_id: UUID of the URL
        days: Number of days to include in analytics
    
    Returns:
        Analytics summary with counts, timeline, devices, locations
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all scans in timeframe
    result = await db.execute(
        select(Scan)
        .filter(Scan.url_id == url_id, Scan.scanned_at >= cutoff_date)
        .order_by(desc(Scan.scanned_at))
    )
    scans = result.scalars().all()
    
    # Calculate metrics
    total_scans = len(scans)
    today = datetime.utcnow().date()
    scans_today = sum(1 for s in scans if s.scanned_at.date() == today)
    
    # Group by location
    locations: Dict[str, int] = defaultdict(int)
    countries: Dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.country:
            countries[scan.country] += 1
        if scan.city and scan.country:
            locations[f"{scan.city}, {scan.country}"] += 1
    
    top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]
    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Group by device
    devices: Dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.device_type:
            devices[scan.device_type] += 1
    
    # Group by browser
    browsers: Dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.browser:
            # Extract just the browser name
            browser_name = scan.browser.split()[0] if scan.browser else "Unknown"
            browsers[browser_name] += 1
    
    # Group by OS
    operating_systems: Dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.os:
            os_name = scan.os.split()[0] if scan.os else "Unknown"
            operating_systems[os_name] += 1
    
    # Timeline (scans per day)
    timeline: Dict[str, int] = defaultdict(int)
    for scan in scans:
        date_key = scan.scanned_at.strftime("%Y-%m-%d")
        timeline[date_key] += 1
    
    # Fill in missing days with 0
    timeline_filled = []
    current_date = cutoff_date.date()
    while current_date <= today:
        date_str = current_date.strftime("%Y-%m-%d")
        timeline_filled.append({
            "date": date_str,
            "count": timeline.get(date_str, 0)
        })
        current_date += timedelta(days=1)
    
    # Recent scans (last 20)
    recent_scans = [
        {
            "scanned_at": scan.scanned_at.isoformat(),
            "country": scan.country,
            "city": scan.city,
            "device": scan.device_type,
            "browser": scan.browser,
            "os": scan.os
        }
        for scan in scans[:20]
    ]
    
    # Hour of day distribution
    hours: Dict[int, int] = defaultdict(int)
    for scan in scans:
        hours[scan.scanned_at.hour] += 1
    
    hour_distribution = [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]
    
    # Day of week distribution
    weekdays: Dict[int, int] = defaultdict(int)
    for scan in scans:
        weekdays[scan.scanned_at.weekday()] += 1
    
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_distribution = [
        {"day": weekday_names[i], "count": weekdays.get(i, 0)}
        for i in range(7)
    ]
    
    return {
        "total_scans": total_scans,
        "scans_today": scans_today,
        "period_days": days,
        "top_locations": top_locations,
        "top_countries": top_countries,
        "devices": dict(devices),
        "browsers": dict(browsers),
        "operating_systems": dict(operating_systems),
        "timeline": timeline_filled,
        "hour_distribution": hour_distribution,
        "weekday_distribution": weekday_distribution,
        "recent_scans": recent_scans
    }


async def get_scans_timeline(
    db: AsyncSession,
    url_id: str,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get scans over time for charting.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Scan.scanned_at)
        .filter(Scan.url_id == url_id, Scan.scanned_at >= cutoff_date)
    )
    
    scans = result.scalars().all()
    
    timeline: Dict[str, int] = defaultdict(int)
    for scan_time in scans:
        date_key = scan_time.strftime("%Y-%m-%d")
        timeline[date_key] += 1
    
    # Fill missing days
    today = datetime.utcnow().date()
    current = cutoff_date.date()
    
    result_list = []
    while current <= today:
        date_str = current.strftime("%Y-%m-%d")
        result_list.append({
            "date": date_str,
            "scans": timeline.get(date_str, 0)
        })
        current += timedelta(days=1)
    
    return result_list
