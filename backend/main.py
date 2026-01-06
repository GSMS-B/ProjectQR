"""
QRSecure - FastAPI Application Entry Point
A QR Code Management Platform with Analytics, Dynamic URLs, and Security Features.
"""

import os
import sys

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config import get_settings
from database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🚀 Starting QRSecure...")
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    # Create qr_codes directory if it doesn't exist
    qr_dir = os.path.join(os.path.dirname(__file__), "qr_codes")
    os.makedirs(qr_dir, exist_ok=True)
    print("✅ QR codes directory ready")
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    print("✅ QRSecure is ready!")
    print(f"📍 Running at: {settings.app_url}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down QRSecure...")


# Initialize FastAPI app
app = FastAPI(
    title="QRSecure API",
    description="QR Code Management Platform with Analytics, Dynamic URLs, and Security Features",
    version="1.0.0",
    lifespan=lifespan
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
qr_codes_dir = os.path.join(os.path.dirname(__file__), "qr_codes")

# Create directories if they don't exist
os.makedirs(frontend_dir, exist_ok=True)
os.makedirs(qr_codes_dir, exist_ok=True)

# Mount QR codes directory
app.mount("/qr_codes", StaticFiles(directory=qr_codes_dir), name="qr_codes")

# Mount frontend static files (CSS, JS)
if os.path.exists(os.path.join(frontend_dir, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")

if os.path.exists(os.path.join(frontend_dir, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")


# Import and include routers
from routes.auth import router as auth_router
from routes.qr import router as qr_router
from routes.analytics import router as analytics_router
from routes.redirect import router as redirect_router

app.include_router(auth_router)
app.include_router(qr_router)
app.include_router(analytics_router)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "QRSecure"
    }


# API info endpoint
@app.get("/api", tags=["API"])
async def api_info():
    """API information endpoint."""
    return {
        "name": "QRSecure API",
        "version": "1.0.0",
        "description": "QR Code Management with Analytics, Dynamic URLs & Security",
        "endpoints": {
            "auth": "/api/auth/",
            "qr_codes": "/api/qr/",
            "analytics": "/api/analytics/",
            "docs": "/docs"
        }
    }


# Serve frontend pages
@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def serve_index():
    """Serve the landing page."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    # Fallback minimal landing page
    return HTMLResponse(content=get_minimal_landing_page())


@app.get("/dashboard", response_class=HTMLResponse, tags=["Frontend"])
async def serve_dashboard():
    """Serve the dashboard page."""
    dashboard_path = os.path.join(frontend_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    
    return HTMLResponse(content="<h1>Dashboard - Coming Soon</h1>")


@app.get("/login", response_class=HTMLResponse, tags=["Frontend"])
async def serve_login():
    """Serve the login page."""
    login_path = os.path.join(frontend_dir, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    
    return HTMLResponse(content="<h1>Login - Coming Soon</h1>")


@app.get("/signup", response_class=HTMLResponse, tags=["Frontend"])
async def serve_signup():
    """Serve the signup page."""
    signup_path = os.path.join(frontend_dir, "signup.html")
    if os.path.exists(signup_path):
        return FileResponse(signup_path)
    
    return HTMLResponse(content="<h1>Signup - Coming Soon</h1>")


# Include redirect routes LAST (catch-all for short codes)
app.include_router(redirect_router)


def get_minimal_landing_page() -> str:
    """Return a minimal landing page if frontend files are not yet created."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QRSecure - Smart QR Code Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container { text-align: center; max-width: 600px; }
        h1 {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tagline { font-size: 1.25rem; opacity: 0.8; margin-bottom: 2rem; }
        .features {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
            text-align: left;
        }
        .feature {
            background: rgba(255,255,255,0.05);
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .feature h3 { font-size: 0.9rem; margin-bottom: 0.5rem; color: #667eea; }
        .feature p { font-size: 0.8rem; opacity: 0.7; }
        .cta {
            display: inline-block;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .cta:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4);
        }
        .api-link {
            margin-top: 1rem;
            display: block;
            color: #667eea;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 QRSecure</h1>
        <p class="tagline">Smart QR Codes with Analytics, Dynamic URLs & Security</p>
        
        <div class="features">
            <div class="feature">
                <h3>📊 Analytics</h3>
                <p>Track every scan with location, device & time data</p>
            </div>
            <div class="feature">
                <h3>🔄 Dynamic URLs</h3>
                <p>Update destinations without re-printing QR codes</p>
            </div>
            <div class="feature">
                <h3>🛡️ Security</h3>
                <p>Preview pages with malware detection</p>
            </div>
            <div class="feature">
                <h3>🎨 Customizable</h3>
                <p>Custom colors and logo embedding</p>
            </div>
        </div>
        
        <a href="/docs" class="cta">View API Documentation</a>
        <a href="/api" class="api-link">API Info →</a>
    </div>
</body>
</html>
'''


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
