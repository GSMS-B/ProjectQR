"""
QRSecure QR Code Management Routes
Handles QR code creation, updating, and deletion.
"""

import os
import string
import secrets
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database import get_db
from models import URL, URLHistory, User
from routes.auth import get_current_user, require_auth
from services.qr_generator import generate_qr_code, generate_qr_base64, get_qr_image_path, delete_qr_image
from services.security import validate_url
from config import get_settings

settings = get_settings()

router = APIRouter(prefix="/api/qr", tags=["QR Codes"])


# Request/Response Models
class QRCreateRequest(BaseModel):
    url: HttpUrl
    show_preview: bool = True
    analytics_enabled: bool = True
    custom_title: Optional[str] = None
    expiration_days: Optional[int] = Field(None, ge=1, le=365)
    qr_color: str = "#000000"
    qr_background: str = "#FFFFFF"


class QRUpdateRequest(BaseModel):
    url: Optional[HttpUrl] = None
    show_preview: Optional[bool] = None
    analytics_enabled: Optional[bool] = None
    custom_title: Optional[str] = None
    is_active: Optional[bool] = None


class QRResponse(BaseModel):
    url_id: str
    short_code: str
    short_url: str
    destination: str
    custom_title: Optional[str]
    show_preview: bool
    analytics_enabled: bool
    is_active: bool
    total_scans: int
    created_at: datetime
    updated_at: datetime
    qr_image_url: str
    expiration_date: Optional[datetime]


class QRListResponse(BaseModel):
    count: int
    qr_codes: List[QRResponse]


# Helper Functions
def generate_short_code(length: int = 6) -> str:
    """Generate a random short code."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def is_short_code_unique(db: AsyncSession, short_code: str) -> bool:
    """Check if a short code is unique."""
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    return result.scalar_one_or_none() is None


async def generate_unique_short_code(db: AsyncSession, length: int = 6) -> str:
    """Generate a unique short code."""
    max_attempts = 10
    for _ in range(max_attempts):
        short_code = generate_short_code(length)
        if await is_short_code_unique(db, short_code):
            return short_code
    
    # If we can't find a unique code, try with longer length
    return await generate_unique_short_code(db, length + 1)


# Routes
@router.post("/create", response_model=QRResponse)
async def create_qr(
    request: QRCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    Create a new QR code.
    """
    url_str = str(request.url)
    
    # Validate URL security
    validation = validate_url(url_str, check_reachability=False)
    
    if not validation["is_safe"]:
        raise HTTPException(
            status_code=400,
            detail=f"URL failed security check: {', '.join(validation['errors'])}"
        )
    
    # Generate unique short code
    short_code = await generate_unique_short_code(db)
    
    # Calculate expiration date if set
    expiration_date = None
    if request.expiration_days:
        from datetime import timedelta
        expiration_date = datetime.utcnow() + timedelta(days=request.expiration_days)
    
    # Create URL record
    url_record = URL(
        user_id=user.user_id if user else None,
        short_code=short_code,
        original_url=url_str,
        custom_title=request.custom_title,
        show_preview=request.show_preview,
        analytics_enabled=request.analytics_enabled,
        qr_color=request.qr_color,
        qr_background=request.qr_background,
        expiration_date=expiration_date,
        is_active=True
    )
    
    db.add(url_record)
    await db.commit()
    await db.refresh(url_record)
    
    # Generate QR code image
    qr_url = f"{settings.app_url}/{short_code}"
    generate_qr_code(
        url=qr_url,
        short_code=short_code,
        fill_color=request.qr_color,
        back_color=request.qr_background
    )
    
    return QRResponse(
        url_id=url_record.url_id,
        short_code=short_code,
        short_url=qr_url,
        destination=url_str,
        custom_title=url_record.custom_title,
        show_preview=url_record.show_preview,
        analytics_enabled=url_record.analytics_enabled,
        is_active=url_record.is_active,
        total_scans=0,
        created_at=url_record.created_at,
        updated_at=url_record.updated_at,
        qr_image_url=f"/qr_codes/{short_code}.png",
        expiration_date=url_record.expiration_date
    )


@router.get("/list", response_model=QRListResponse)
async def list_qr_codes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    List all QR codes for the current user.
    """
    result = await db.execute(
        select(URL)
        .filter(URL.user_id == user.user_id)
        .order_by(desc(URL.created_at))
    )
    urls = result.scalars().all()
    
    qr_codes = [
        QRResponse(
            url_id=url.url_id,
            short_code=url.short_code,
            short_url=f"{settings.app_url}/{url.short_code}",
            destination=url.original_url,
            custom_title=url.custom_title,
            show_preview=url.show_preview,
            analytics_enabled=url.analytics_enabled,
            is_active=url.is_active,
            total_scans=url.total_scans,
            created_at=url.created_at,
            updated_at=url.updated_at,
            qr_image_url=f"/qr_codes/{url.short_code}.png",
            expiration_date=url.expiration_date
        )
        for url in urls
    ]
    
    return QRListResponse(count=len(qr_codes), qr_codes=qr_codes)


@router.get("/{short_code}", response_model=QRResponse)
async def get_qr_code(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    Get details of a specific QR code.
    """
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Check ownership if user is logged in
    if user and url.user_id and url.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return QRResponse(
        url_id=url.url_id,
        short_code=url.short_code,
        short_url=f"{settings.app_url}/{url.short_code}",
        destination=url.original_url,
        custom_title=url.custom_title,
        show_preview=url.show_preview,
        analytics_enabled=url.analytics_enabled,
        is_active=url.is_active,
        total_scans=url.total_scans,
        created_at=url.created_at,
        updated_at=url.updated_at,
        qr_image_url=f"/qr_codes/{url.short_code}.png",
        expiration_date=url.expiration_date
    )


@router.put("/{short_code}", response_model=QRResponse)
async def update_qr_code(
    short_code: str,
    request: QRUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Update a QR code's destination or settings (dynamic QR feature).
    """
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Update URL if provided
    if request.url:
        new_url = str(request.url)
        
        # Validate new URL
        validation = validate_url(new_url, check_reachability=False)
        if not validation["is_safe"]:
            raise HTTPException(
                status_code=400,
                detail=f"URL failed security check: {', '.join(validation['errors'])}"
            )
        
        # Save to history
        history = URLHistory(
            url_id=url.url_id,
            old_url=url.original_url,
            new_url=new_url,
            changed_by=user.user_id
        )
        db.add(history)
        
        url.original_url = new_url
    
    # Update other fields if provided
    if request.show_preview is not None:
        url.show_preview = request.show_preview
    
    if request.analytics_enabled is not None:
        url.analytics_enabled = request.analytics_enabled
    
    if request.custom_title is not None:
        url.custom_title = request.custom_title
    
    if request.is_active is not None:
        url.is_active = request.is_active
    
    url.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(url)
    
    return QRResponse(
        url_id=url.url_id,
        short_code=url.short_code,
        short_url=f"{settings.app_url}/{url.short_code}",
        destination=url.original_url,
        custom_title=url.custom_title,
        show_preview=url.show_preview,
        analytics_enabled=url.analytics_enabled,
        is_active=url.is_active,
        total_scans=url.total_scans,
        created_at=url.created_at,
        updated_at=url.updated_at,
        qr_image_url=f"/qr_codes/{url.short_code}.png",
        expiration_date=url.expiration_date
    )


@router.delete("/{short_code}")
async def delete_qr_code(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Delete (deactivate) a QR code.
    """
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Soft delete - deactivate instead of delete
    url.is_active = False
    url.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "QR code deactivated successfully", "short_code": short_code}


@router.get("/{short_code}/download")
async def download_qr_code(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Download the QR code image.
    """
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    qr_path = get_qr_image_path(short_code)
    
    if not qr_path:
        # Regenerate if missing
        qr_url = f"{settings.app_url}/{short_code}"
        qr_path = generate_qr_code(
            url=qr_url,
            short_code=short_code,
            fill_color=url.qr_color,
            back_color=url.qr_background
        )
    
    return FileResponse(
        qr_path,
        media_type="image/png",
        filename=f"qrcode_{short_code}.png"
    )


@router.get("/{short_code}/history")
async def get_url_history(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """
    Get URL change history for a QR code.
    """
    result = await db.execute(
        select(URL).filter(URL.short_code == short_code, URL.user_id == user.user_id)
    )
    url = result.scalar_one_or_none()
    
    if not url:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    history_result = await db.execute(
        select(URLHistory)
        .filter(URLHistory.url_id == url.url_id)
        .order_by(desc(URLHistory.changed_at))
    )
    history = history_result.scalars().all()
    
    return {
        "short_code": short_code,
        "current_url": url.original_url,
        "history": [
            {
                "old_url": h.old_url,
                "new_url": h.new_url,
                "changed_at": h.changed_at.isoformat()
            }
            for h in history
        ]
    }
