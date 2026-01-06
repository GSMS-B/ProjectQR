"""
QRSecure Security Service
Handles URL validation, Safe Browsing API, SSL checks, and domain age verification.
"""

import os
import ssl
import socket
import requests
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, Optional
from functools import lru_cache
import hashlib
import time

from config import get_settings, is_safe_browsing_configured

settings = get_settings()

# Cache for security checks (avoid repeated API calls)
_security_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600  # 1 hour


def _get_cache_key(url: str) -> str:
    """Generate a cache key from URL."""
    return hashlib.md5(url.encode()).hexdigest()


def _is_cache_valid(cache_entry: Dict) -> bool:
    """Check if cache entry is still valid."""
    return time.time() - cache_entry.get('timestamp', 0) < CACHE_TTL


def validate_url_format(url: str) -> Dict[str, Any]:
    """
    Validate basic URL format.
    
    Returns:
        dict with is_valid and reason
    """
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return {"is_valid": False, "reason": "Missing URL scheme (http/https)"}
        
        if parsed.scheme not in ["http", "https"]:
            return {"is_valid": False, "reason": "Invalid scheme. Only http/https allowed"}
        
        if not parsed.netloc:
            return {"is_valid": False, "reason": "Missing domain"}
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "javascript:",
            "data:",
            "vbscript:",
            "file://",
        ]
        
        for pattern in suspicious_patterns:
            if pattern in url.lower():
                return {"is_valid": False, "reason": f"Suspicious URL pattern detected: {pattern}"}
        
        return {"is_valid": True, "reason": None}
    except Exception as e:
        return {"is_valid": False, "reason": f"Invalid URL: {str(e)}"}


def check_url_reachable(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Check if URL is reachable.
    
    Returns:
        dict with is_reachable, status_code, and error
    """
    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "QRSecure/1.0"}
        )
        
        return {
            "is_reachable": response.status_code < 400,
            "status_code": response.status_code,
            "final_url": response.url,
            "error": None
        }
    except requests.exceptions.Timeout:
        return {
            "is_reachable": False,
            "status_code": None,
            "error": "Connection timeout"
        }
    except requests.exceptions.SSLError:
        return {
            "is_reachable": False,
            "status_code": None,
            "error": "SSL certificate error"
        }
    except requests.exceptions.ConnectionError:
        return {
            "is_reachable": False,
            "status_code": None,
            "error": "Could not connect to server"
        }
    except Exception as e:
        return {
            "is_reachable": False,
            "status_code": None,
            "error": str(e)
        }


def check_safe_browsing(url: str) -> Dict[str, Any]:
    """
    Check URL against Google Safe Browsing API.
    
    Returns:
        dict with is_safe and threats list
    """
    if not is_safe_browsing_configured():
        return {
            "is_safe": True,
            "threats": [],
            "note": "Safe Browsing API not configured"
        }
    
    # Check cache first
    cache_key = _get_cache_key(url)
    if cache_key in _security_cache and _is_cache_valid(_security_cache[cache_key]):
        return _security_cache[cache_key]['safe_browsing']
    
    api_key = settings.google_safe_browsing_key
    endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    
    payload = {
        "client": {
            "clientId": "qrsecure",
            "clientVersion": "1.0.0"
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION"
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    
    try:
        response = requests.post(
            f"{endpoint}?key={api_key}",
            json=payload,
            timeout=5
        )
        
        if response.status_code != 200:
            return {"is_safe": True, "threats": [], "error": f"API error: {response.status_code}"}
        
        data = response.json()
        
        if "matches" in data and len(data["matches"]) > 0:
            threats = [match["threatType"] for match in data["matches"]]
            result = {"is_safe": False, "threats": threats}
        else:
            result = {"is_safe": True, "threats": []}
        
        # Cache the result
        if cache_key not in _security_cache:
            _security_cache[cache_key] = {}
        _security_cache[cache_key]['safe_browsing'] = result
        _security_cache[cache_key]['timestamp'] = time.time()
        
        return result
    
    except Exception as e:
        return {"is_safe": True, "threats": [], "error": str(e)}


def check_ssl_certificate(url: str) -> Dict[str, Any]:
    """
    Check SSL certificate validity.
    
    Returns:
        dict with has_ssl, issuer, valid_until, and is_valid
    """
    parsed = urlparse(url)
    
    if parsed.scheme != "https":
        return {
            "has_ssl": False,
            "reason": "URL is not HTTPS"
        }
    
    domain = parsed.netloc
    
    # Remove port if present
    if ":" in domain:
        domain = domain.split(":")[0]
    
    try:
        context = ssl.create_default_context()
        
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                
                # Parse expiration date
                not_after = cert.get('notAfter')
                issuer_info = dict(x[0] for x in cert.get('issuer', []))
                
                # Check if certificate is expired
                if not_after:
                    expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    is_valid = expiry > datetime.utcnow()
                else:
                    is_valid = True
                
                return {
                    "has_ssl": True,
                    "issuer": issuer_info.get('organizationName', 'Unknown'),
                    "valid_until": not_after,
                    "is_valid": is_valid
                }
    
    except ssl.SSLCertVerificationError as e:
        return {
            "has_ssl": True,
            "is_valid": False,
            "error": "Certificate verification failed"
        }
    except socket.timeout:
        return {
            "has_ssl": False,
            "error": "Connection timeout"
        }
    except socket.gaierror:
        return {
            "has_ssl": False,
            "error": "Could not resolve domain"
        }
    except Exception as e:
        return {
            "has_ssl": False,
            "error": str(e)
        }


def check_domain_age(url: str) -> Dict[str, Any]:
    """
    Check domain registration age using WHOIS.
    
    Returns:
        dict with age_days, created, and is_new flag
    """
    parsed = urlparse(url)
    domain = parsed.netloc
    
    # Remove port if present
    if ":" in domain:
        domain = domain.split(":")[0]
    
    # Remove www prefix
    if domain.startswith("www."):
        domain = domain[4:]
    
    try:
        import whois
        
        w = whois.whois(domain)
        creation_date = w.creation_date
        
        # Handle list of dates (some registrars return multiple)
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        
        if creation_date:
            age_days = (datetime.now() - creation_date).days
            
            return {
                "age_days": age_days,
                "created": creation_date.strftime("%Y-%m-%d"),
                "is_new": age_days < 30,
                "is_suspicious": age_days < 7  # Very new domains are suspicious
            }
        else:
            return {
                "age_days": None,
                "error": "Creation date not available"
            }
    
    except Exception as e:
        return {
            "age_days": None,
            "error": str(e)
        }


def validate_url(url: str, check_reachability: bool = True) -> Dict[str, Any]:
    """
    Comprehensive URL validation combining all security checks.
    
    Args:
        url: URL to validate
        check_reachability: Whether to check if URL is reachable (slower)
    
    Returns:
        Complete validation result with is_safe flag
    """
    result = {
        "url": url,
        "is_safe": True,
        "warnings": [],
        "errors": [],
        "details": {}
    }
    
    # 1. Format validation
    format_check = validate_url_format(url)
    result["details"]["format"] = format_check
    
    if not format_check["is_valid"]:
        result["is_safe"] = False
        result["errors"].append(format_check["reason"])
        return result
    
    # 2. Safe Browsing check
    safe_browsing = check_safe_browsing(url)
    result["details"]["safe_browsing"] = safe_browsing
    
    if not safe_browsing.get("is_safe", True):
        result["is_safe"] = False
        result["errors"].append(f"Flagged as malicious: {', '.join(safe_browsing['threats'])}")
    
    # 3. SSL certificate check
    ssl_check = check_ssl_certificate(url)
    result["details"]["ssl"] = ssl_check
    
    if not ssl_check.get("has_ssl", False):
        result["warnings"].append("No HTTPS (connection not encrypted)")
    elif not ssl_check.get("is_valid", True):
        result["warnings"].append("SSL certificate issue detected")
    
    # 4. Domain age check
    domain_age = check_domain_age(url)
    result["details"]["domain_age"] = domain_age
    
    if domain_age.get("is_suspicious"):
        result["warnings"].append("Domain registered less than 7 days ago")
    elif domain_age.get("is_new"):
        result["warnings"].append("Domain registered less than 30 days ago")
    
    # 5. Reachability check (optional, slower)
    if check_reachability:
        reachable = check_url_reachable(url)
        result["details"]["reachability"] = reachable
        
        if not reachable.get("is_reachable", False):
            result["warnings"].append(f"URL may not be reachable: {reachable.get('error', 'Unknown error')}")
    
    return result


def get_security_info(url: str) -> Dict[str, Any]:
    """
    Get security information for preview page display.
    Lighter version of validate_url for quick display.
    """
    ssl_info = check_ssl_certificate(url)
    safe_browsing = check_safe_browsing(url)
    domain_age = check_domain_age(url)
    
    return {
        "has_ssl": ssl_info.get("has_ssl", False),
        "ssl_issuer": ssl_info.get("issuer"),
        "is_safe": safe_browsing.get("is_safe", True),
        "threats": safe_browsing.get("threats", []),
        "domain_age": domain_age.get("age_days"),
        "domain_created": domain_age.get("created"),
        "is_new_domain": domain_age.get("is_new", False)
    }
