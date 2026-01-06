"""
QRSecure Geolocation Service
Handles IP to location lookup using GeoLite2 database.
"""

import os
from typing import Dict, Any, Optional
from config import get_settings, is_geolite_configured

settings = get_settings()

# GeoIP reader instance (lazy loaded)
_reader = None


def _get_reader():
    """Get or initialize the GeoIP reader."""
    global _reader
    
    if _reader is not None:
        return _reader
    
    if not is_geolite_configured():
        return None
    
    try:
        import geoip2.database
        _reader = geoip2.database.Reader(settings.geolite2_db_path)
        return _reader
    except Exception as e:
        print(f"Warning: Could not load GeoLite2 database: {e}")
        return None


def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """
    Get geographic location from IP address.
    
    Args:
        ip_address: IPv4 or IPv6 address
    
    Returns:
        dict with country, city, coordinates, etc.
    """
    # Skip private/local IPs
    if _is_private_ip(ip_address):
        return {
            "country": "Local",
            "country_code": "XX",
            "city": "Local Network",
            "latitude": None,
            "longitude": None,
            "is_local": True
        }
    
    reader = _get_reader()
    
    if reader is None:
        return {
            "country": "Unknown",
            "country_code": None,
            "city": "Unknown",
            "latitude": None,
            "longitude": None,
            "note": "GeoLite2 database not configured"
        }
    
    try:
        response = reader.city(ip_address)
        
        return {
            "country": response.country.name or "Unknown",
            "country_code": response.country.iso_code,
            "city": response.city.name or "Unknown",
            "region": response.subdivisions.most_specific.name if response.subdivisions else None,
            "latitude": response.location.latitude,
            "longitude": response.location.longitude,
            "timezone": response.location.time_zone,
            "postal_code": response.postal.code if response.postal else None
        }
    
    except Exception as e:
        return {
            "country": "Unknown",
            "country_code": None,
            "city": "Unknown",
            "latitude": None,
            "longitude": None,
            "error": str(e)
        }


def _is_private_ip(ip_address: str) -> bool:
    """
    Check if IP address is private/local.
    """
    private_prefixes = [
        "10.",
        "172.16.", "172.17.", "172.18.", "172.19.",
        "172.20.", "172.21.", "172.22.", "172.23.",
        "172.24.", "172.25.", "172.26.", "172.27.",
        "172.28.", "172.29.", "172.30.", "172.31.",
        "192.168.",
        "127.",
        "0.",
        "::1",
        "fe80:",
        "fc00:",
        "fd00:",
    ]
    
    for prefix in private_prefixes:
        if ip_address.startswith(prefix):
            return True
    
    return ip_address in ["localhost", "::1", "0.0.0.0"]


def close_reader():
    """Close the GeoIP reader (for cleanup)."""
    global _reader
    if _reader is not None:
        _reader.close()
        _reader = None
