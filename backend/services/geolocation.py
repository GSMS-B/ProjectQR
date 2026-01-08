"""
QRSecure Geolocation Service
Handles IP to location lookup using GeoLite2 database with ip-api.com fallback.
"""

import os
import httpx
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
        print(f"GeoLite2 not configured. Path: {settings.geolite2_db_path}, Exists: {os.path.exists(settings.geolite2_db_path)}")
        return None
    
    try:
        import geoip2.database
        _reader = geoip2.database.Reader(settings.geolite2_db_path)
        print(f"GeoLite2 database loaded successfully from: {settings.geolite2_db_path}")
        return _reader
    except Exception as e:
        print(f"Warning: Could not load GeoLite2 database: {e}")
        return None


async def get_location_from_ip_async(ip_address: str) -> Dict[str, Any]:
    """
    Get geographic location from IP address (async version with API fallback).
    
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
    
    # Try GeoLite2 first
    result = _lookup_geolite2(ip_address)
    
    # If GeoLite2 failed or returned Unknown, try fallback API
    if result.get("country") == "Unknown" or result.get("country") is None:
        api_result = await _lookup_ip_api(ip_address)
        if api_result.get("country") != "Unknown":
            return api_result
    
    return result


def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """
    Get geographic location from IP address (sync version).
    Falls back to ip-api.com if GeoLite2 fails.
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
    
    # Try GeoLite2 first
    result = _lookup_geolite2(ip_address)
    
    # If GeoLite2 failed, try sync API call
    if result.get("country") == "Unknown" or result.get("country") is None:
        api_result = _lookup_ip_api_sync(ip_address)
        if api_result.get("country") != "Unknown":
            return api_result
    
    return result


def _lookup_geolite2(ip_address: str) -> Dict[str, Any]:
    """Lookup IP using local GeoLite2 database."""
    reader = _get_reader()
    
    if reader is None:
        return {
            "country": "Unknown",
            "country_code": None,
            "city": "Unknown",
            "latitude": None,
            "longitude": None,
            "source": "none"
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
            "postal_code": response.postal.code if response.postal else None,
            "source": "geolite2"
        }
    
    except Exception as e:
        print(f"GeoLite2 lookup failed for {ip_address}: {e}")
        return {
            "country": "Unknown",
            "country_code": None,
            "city": "Unknown",
            "latitude": None,
            "longitude": None,
            "error": str(e),
            "source": "geolite2_error"
        }


async def _lookup_ip_api(ip_address: str) -> Dict[str, Any]:
    """Lookup IP using ip-api.com (free, 45 req/min, no key required)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://ip-api.com/json/{ip_address}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status") == "success":
                    return {
                        "country": data.get("country", "Unknown"),
                        "country_code": data.get("countryCode"),
                        "city": data.get("city", "Unknown"),
                        "region": data.get("regionName"),
                        "latitude": data.get("lat"),
                        "longitude": data.get("lon"),
                        "timezone": data.get("timezone"),
                        "isp": data.get("isp"),
                        "source": "ip-api.com"
                    }
    except Exception as e:
        print(f"ip-api.com lookup failed for {ip_address}: {e}")
    
    return {
        "country": "Unknown",
        "country_code": None,
        "city": "Unknown",
        "latitude": None,
        "longitude": None,
        "source": "api_error"
    }


def _lookup_ip_api_sync(ip_address: str) -> Dict[str, Any]:
    """Sync version of ip-api.com lookup."""
    try:
        import requests
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == "success":
                return {
                    "country": data.get("country", "Unknown"),
                    "country_code": data.get("countryCode"),
                    "city": data.get("city", "Unknown"),
                    "region": data.get("regionName"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "source": "ip-api.com"
                }
    except Exception as e:
        print(f"ip-api.com sync lookup failed for {ip_address}: {e}")
    
    return {
        "country": "Unknown",
        "country_code": None,
        "city": "Unknown",
        "latitude": None,
        "longitude": None,
        "source": "api_error"
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

