"""
QRSecure Database Models
SQLAlchemy ORM models for all database tables.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, func
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database import Base


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class User(Base):
    """
    User model - stores user account information.
    Works alongside Supabase Auth for external auth.
    """
    __tablename__ = "users"
    
    user_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=generate_uuid
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False,
        index=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True  # Nullable for Supabase auth users
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    subscription_tier: Mapped[str] = mapped_column(
        String(50), 
        default="free"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True
    )
    
    # Relationships
    urls: Mapped[List["URL"]] = relationship(
        "URL", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(email='{self.email}')>"


class URL(Base):
    """
    URL model - stores QR code destination URLs and settings.
    """
    __tablename__ = "urls"
    
    url_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=generate_uuid
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    short_code: Mapped[str] = mapped_column(
        String(10), 
        unique=True, 
        nullable=False,
        index=True
    )
    original_url: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    custom_title: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    
    # Settings
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True
    )
    show_preview: Mapped[bool] = mapped_column(
        Boolean, 
        default=True
    )
    analytics_enabled: Mapped[bool] = mapped_column(
        Boolean, 
        default=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True
    )
    
    # QR Code Customization
    qr_color: Mapped[str] = mapped_column(
        String(7), 
        default="#000000"  # Black
    )
    qr_background: Mapped[str] = mapped_column(
        String(7), 
        default="#FFFFFF"  # White
    )
    
    # Statistics
    total_scans: Mapped[int] = mapped_column(
        Integer, 
        default=0
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User", 
        back_populates="urls"
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan", 
        back_populates="url",
        cascade="all, delete-orphan"
    )
    history: Mapped[List["URLHistory"]] = relationship(
        "URLHistory", 
        back_populates="url",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<URL(short_code='{self.short_code}', destination='{self.original_url[:50]}...')>"


class Scan(Base):
    """
    Scan model - stores analytics for each QR code scan.
    """
    __tablename__ = "scans"
    
    scan_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=generate_uuid
    )
    url_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("urls.url_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        index=True
    )
    
    # Network Information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True
    )
    
    # Geolocation
    country: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True
    )
    country_code: Mapped[Optional[str]] = mapped_column(
        String(3), 
        nullable=True
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )
    
    # Device Information
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50), 
        nullable=True
    )
    os: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True
    )
    browser: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True
    )
    
    # Referrer
    referrer: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True
    )
    
    # Relationships
    url: Mapped["URL"] = relationship(
        "URL", 
        back_populates="scans"
    )
    
    def __repr__(self) -> str:
        return f"<Scan(url_id='{self.url_id}', at='{self.scanned_at}')>"


class URLHistory(Base):
    """
    URL History model - tracks destination URL changes for audit trail.
    """
    __tablename__ = "url_history"
    
    history_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=generate_uuid
    )
    url_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("urls.url_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    old_url: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    new_url: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(36), 
        nullable=True  # User ID who made the change
    )
    
    # Relationships
    url: Mapped["URL"] = relationship(
        "URL", 
        back_populates="history"
    )
    
    def __repr__(self) -> str:
        return f"<URLHistory(url_id='{self.url_id}', at='{self.changed_at}')>"


class Report(Base):
    """
    Report model - stores user reports for suspicious links.
    """
    __tablename__ = "reports"
    
    report_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=generate_uuid
    )
    url_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("urls.url_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reporter_ip: Mapped[Optional[str]] = mapped_column(
        String(45), 
        nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    status: Mapped[str] = mapped_column(
        String(20), 
        default="pending"  # pending, reviewed, dismissed, actioned
    )
    
    def __repr__(self) -> str:
        return f"<Report(url_id='{self.url_id}', status='{self.status}')>"


# Create indexes for performance
Index("idx_scans_url_date", Scan.url_id, Scan.scanned_at)
Index("idx_urls_user_active", URL.user_id, URL.is_active)
