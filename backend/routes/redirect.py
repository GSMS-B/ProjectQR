"""
QRSecure Redirect Routes
Handles QR code scanning, preview pages, and redirects.
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database import get_db
from models import URL, Report
from services.analytics import log_scan
from services.security import get_security_info

router = APIRouter(tags=["Redirect"])


@router.get("/{short_code}")
async def redirect_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Main redirect endpoint - handles QR code scans.
    Either shows preview page or redirects directly based on settings.
    """
    # Look up short code
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url_data = result.scalar_one_or_none()
    
    if not url_data:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    if not url_data.is_active:
        raise HTTPException(status_code=410, detail="This QR code has been deactivated")
    
    # Check expiration
    if url_data.expiration_date and datetime.utcnow() > url_data.expiration_date:
        raise HTTPException(status_code=410, detail="This QR code has expired")
    
    # Log analytics (non-blocking)
    if url_data.analytics_enabled:
        try:
            # Get real IP from header (for Render/Proxies) or fallback to connection IP
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            else:
                ip = request.client.host if request.client else "0.0.0.0"
                
            user_agent = request.headers.get("user-agent", "")
            referrer = request.headers.get("referer")
            
            await log_scan(
                db=db,
                url_id=url_data.url_id,
                ip_address=ip,
                user_agent=user_agent,
                referrer=referrer
            )
        except Exception as e:
            # Don't fail the redirect if analytics fails
            print(f"Analytics logging error: {e}")
    
    # Show preview or direct redirect
    if url_data.show_preview:
        return RedirectResponse(url=f"/preview/{short_code}", status_code=302)
    else:
        return RedirectResponse(url=url_data.original_url, status_code=302)


@router.get("/preview/{short_code}", response_class=HTMLResponse)
async def preview_page(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Show preview page with security information before redirecting.
    """
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url_data = result.scalar_one_or_none()
    
    if not url_data:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Get security information
    security = get_security_info(url_data.original_url)
    
    # Extract domain for display
    from urllib.parse import urlparse
    parsed = urlparse(url_data.original_url)
    display_domain = parsed.netloc
    
    # Build security badges HTML
    ssl_badge_class = "success" if security["has_ssl"] else "warning"
    ssl_icon = "✓" if security["has_ssl"] else "⚠"
    ssl_text = "Secure (HTTPS)" if security["has_ssl"] else "Not Secure (HTTP)"
    
    safe_badge_class = "success" if security["is_safe"] else "danger"
    safe_icon = "✓" if security["is_safe"] else "✕"
    safe_text = "Verified Safe" if security["is_safe"] else f"Security Warning: {', '.join(security.get('threats', []))}"
    
    domain_age_html = ""
    if security.get("domain_age"):
        age_class = "warning" if security.get("is_new_domain") else "success"
        age_icon = "⚠" if security.get("is_new_domain") else "✓"
        domain_age_html = f'''
            <div class="badge {age_class}">
                <span class="badge-icon">{age_icon}</span>
                <span>Domain Age: {security["domain_age"]} days</span>
            </div>
        '''
    
    title = url_data.custom_title or display_domain
    
    html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Preview - QRSecure</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 20px;
        }}
        
        .preview-container {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            padding: 40px;
            border-radius: 24px;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.4);
            max-width: 480px;
            width: 100%;
            text-align: center;
            animation: slideUp 0.5s ease-out;
        }}
        
        @keyframes slideUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .lock-icon {{
            font-size: 56px;
            margin-bottom: 16px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}
        
        h2 {{
            color: #1a1a2e;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .subtitle {{
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        
        .destination {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 18px;
            font-weight: 600;
            margin: 16px 0;
            word-break: break-all;
            padding: 16px;
            border-radius: 12px;
            background-color: #f8f9fa;
            -webkit-text-fill-color: initial;
            color: #667eea;
        }}
        
        .security-badges {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin: 24px 0;
            text-align: left;
        }}
        
        .badge {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .badge-icon {{
            font-size: 16px;
        }}
        
        .badge.success {{
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
        }}
        
        .badge.warning {{
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            color: #856404;
        }}
        
        .badge.danger {{
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            color: #721c24;
        }}
        
        .buttons {{
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }}
        
        .btn {{
            flex: 1;
            padding: 14px 24px;
            font-size: 15px;
            font-weight: 600;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
        }}
        
        .btn-secondary {{
            background: #e9ecef;
            color: #495057;
        }}
        
        .btn-secondary:hover {{
            background: #dee2e6;
        }}
        
        .countdown {{
            color: #888;
            font-size: 13px;
            margin-top: 20px;
        }}
        
        #seconds {{
            font-weight: 700;
            color: #667eea;
        }}
        
        .report-link {{
            display: inline-block;
            margin-top: 20px;
            color: #999;
            text-decoration: none;
            font-size: 13px;
            transition: color 0.3s;
        }}
        
        .report-link:hover {{
            color: #dc3545;
        }}
        
        @media (max-width: 480px) {{
            .preview-container {{
                padding: 24px;
            }}
            
            .buttons {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="preview-container">
        <div class="lock-icon">🔒</div>
        <h2>Link Preview</h2>
        <p class="subtitle">You're about to visit:</p>
        
        <div class="destination">{display_domain}</div>
        
        <div class="security-badges">
            <div class="badge {ssl_badge_class}">
                <span class="badge-icon">{ssl_icon}</span>
                <span>{ssl_text}</span>
            </div>
            <div class="badge {safe_badge_class}">
                <span class="badge-icon">{safe_icon}</span>
                <span>{safe_text}</span>
            </div>
            {domain_age_html}
        </div>
        
        <div class="buttons">
            <button class="btn btn-primary" onclick="continueToSite()">
                Continue to Site
            </button>
            <button class="btn btn-secondary" onclick="goBack()">
                Go Back
            </button>
        </div>
        
        <div class="countdown">
            Auto-redirecting in <span id="seconds">5</span> seconds...
        </div>
        
        <a href="/report/{short_code}" class="report-link">
            🚩 Report suspicious link
        </a>
    </div>
    
    <script>
        let seconds = 5;
        const countdownElement = document.getElementById('seconds');
        const destinationUrl = "{url_data.original_url}";
        
        const countdown = setInterval(() => {{
            seconds--;
            countdownElement.textContent = seconds;
            
            if (seconds <= 0) {{
                clearInterval(countdown);
                continueToSite();
            }}
        }}, 1000);
        
        function continueToSite() {{
            clearInterval(countdown);
            window.location.href = destinationUrl;
        }}
        
        function goBack() {{
            clearInterval(countdown);
            if (window.history.length > 1) {{
                window.history.back();
            }} else {{
                window.close();
            }}
        }}
    </script>
</body>
</html>
'''
    
    return HTMLResponse(content=html_content)


@router.get("/report/{short_code}", response_class=HTMLResponse)
async def report_page(short_code: str, db: AsyncSession = Depends(get_db)):
    """Show report form for suspicious links."""
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url_data = result.scalar_one_or_none()
    
    if not url_data:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Report Link - QRSecure</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 20px;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 24px;
            max-width: 480px;
            width: 100%;
        }}
        h2 {{ color: #dc3545; margin-bottom: 20px; }}
        .url {{ background: #f8f9fa; padding: 12px; border-radius: 8px; margin-bottom: 20px; word-break: break-all; }}
        label {{ display: block; margin-bottom: 8px; font-weight: 500; }}
        textarea {{
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-family: inherit;
            font-size: 14px;
            resize: vertical;
            min-height: 100px;
        }}
        textarea:focus {{ outline: none; border-color: #667eea; }}
        .btn {{
            width: 100%;
            padding: 14px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
        }}
        .btn:hover {{ background: #c82333; }}
        .back {{ display: block; text-align: center; margin-top: 16px; color: #666; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🚩 Report Suspicious Link</h2>
        <p style="margin-bottom: 20px;">If you believe this link is malicious, please report it.</p>
        <div class="url">{url_data.original_url}</div>
        <form action="/api/report/{short_code}" method="POST">
            <label for="reason">Why are you reporting this link?</label>
            <textarea name="reason" id="reason" placeholder="Describe why you think this link is suspicious..."></textarea>
            <button type="submit" class="btn">Submit Report</button>
        </form>
        <a href="/preview/{short_code}" class="back">← Back to preview</a>
    </div>
</body>
</html>
'''
    
    return HTMLResponse(content=html_content)


@router.post("/api/report/{short_code}")
async def submit_report(
    short_code: str,
    request: Request,
    reason: str = Form(default=""),
    db: AsyncSession = Depends(get_db)
):
    """Submit a report for a suspicious link."""
    result = await db.execute(select(URL).filter(URL.short_code == short_code))
    url_data = result.scalar_one_or_none()
    
    if not url_data:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    # Create report
    report = Report(
        url_id=url_data.url_id,
        reporter_ip=request.client.host if request.client else None,
        reason=reason,
        status="pending"
    )
    
    db.add(report)
    await db.commit()
    
    # Return thank you page
    html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Report Submitted - QRSecure</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            text-align: center;
            color: white;
        }
        .container { padding: 40px; }
        h2 { font-size: 48px; margin-bottom: 20px; }
        p { font-size: 18px; opacity: 0.9; }
    </style>
</head>
<body>
    <div class="container">
        <h2>✓</h2>
        <p>Thank you for your report. We will review it shortly.</p>
    </div>
</body>
</html>
'''
    
    return HTMLResponse(content=html_content)
