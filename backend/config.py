"""
QRSecure Configuration Module
Handles environment variables and application settings.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    supabase_url: str = Field(default="", env="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", env="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", env="SUPABASE_SERVICE_KEY")
    
    # Google Safe Browsing
    google_safe_browsing_key: str = Field(default="", env="GOOGLE_SAFE_BROWSING_KEY")
    
    # App Configuration
    app_url: str = Field(default="http://localhost:8000", env="APP_URL")
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    debug: bool = Field(default=False, env="DEBUG")
    
    # GeoLite2 Database - use absolute path based on this file's location
    _backend_dir: str = os.path.dirname(os.path.abspath(__file__))
    geolite2_db_path: str = Field(
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "GeoLite2-City.mmdb"),
        env="GEOLITE2_DB_PATH"
    )
    
    # Database (SQLite for local, can override with PostgreSQL)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./qrsecure.db",
        env="DATABASE_URL"
    )
    
    # JWT Settings
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid reading .env file on every request.
    """
    return Settings()


# Convenience function to check if services are configured
def is_supabase_configured() -> bool:
    """Check if Supabase credentials are provided."""
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_anon_key)


def is_safe_browsing_configured() -> bool:
    """Check if Google Safe Browsing API is configured."""
    settings = get_settings()
    return bool(settings.google_safe_browsing_key)


def is_geolite_configured() -> bool:
    """Check if GeoLite2 database is available."""
    settings = get_settings()
    return os.path.exists(settings.geolite2_db_path)
