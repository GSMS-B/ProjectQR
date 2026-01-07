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
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'JetBrains Mono', monospace;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #ffffff;
            padding: 20px;
        }}
        
        .preview-container {{
            background: #ffffff;
            border: 1px solid #e5e5e5;
            padding: 48px;
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
            margin-bottom: 24px;
        }}
        
        .lock-icon svg {{
            width: 48px;
            height: 48px;
            stroke: #1a1a1a;
        }}
        
        h2 {{
            color: #1a1a1a;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .subtitle {{
            color: #666666;
            font-size: 0.875rem;
            margin-bottom: 24px;
        }}
        
        .destination {{
            background: #fafafa;
            border: 1px solid #e5e5e5;
            padding: 16px;
            font-size: 1rem;
            font-weight: 600;
            color: #FF6B2C;
            word-break: break-all;
            margin-bottom: 24px;
        }}
        
        .security-badges {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 32px;
            text-align: left;
        }}
        
        .badge {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            font-size: 0.875rem;
            font-weight: 500;
            border-left: 3px solid;
        }}
        
        .badge-icon {{
            font-size: 14px;
        }}
        
        .badge.success {{
            background: rgba(16, 185, 129, 0.1);
            border-left-color: #10b981;
            color: #065f46;
        }}
        
        .badge.warning {{
            background: rgba(245, 158, 11, 0.1);
            border-left-color: #f59e0b;
            color: #92400e;
        }}
        
        .badge.danger {{
            background: rgba(239, 68, 68, 0.1);
            border-left-color: #ef4444;
            color: #991b1b;
        }}
        
        .buttons {{
            display: flex;
            gap: 12px;
        }}
        
        .btn {{
            flex: 1;
            padding: 14px 24px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .btn-primary {{
            background: #FF6B2C;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #e55a1f;
            transform: translateY(-2px);
        }}
        
        .btn-secondary {{
            background: #ffffff;
            color: #1a1a1a;
            border: 1px solid #e5e5e5;
        }}
        
        .btn-secondary:hover {{
            background: #fafafa;
        }}
        
        .countdown {{
            color: #999999;
            font-size: 0.75rem;
            margin-top: 24px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        #seconds {{
            font-weight: 700;
            color: #FF6B2C;
        }}
        
        .report-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 24px;
            color: #999999;
            text-decoration: none;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: color 0.3s;
        }}
        
        .report-link:hover {{
            color: #ef4444;
        }}
        
        @media (max-width: 480px) {{
            .preview-container {{
                padding: 32px 24px;
            }}
            
            .buttons {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="preview-container">
        <div class="lock-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
        </div>
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
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>
            Report suspicious link
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
