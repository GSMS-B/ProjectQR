# QRSecure 🔒

A smart QR Code Management Platform with Analytics, Dynamic URLs, and Security Features.

![QRSecure](https://img.shields.io/badge/QRSecure-v1.0.0-667eea)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)

## Features

- **📊 Real-Time Analytics** - Track every scan with location, device, browser, and time data
- **🔄 Dynamic URLs** - Update destinations without regenerating QR codes
- **🛡️ Security First** - Google Safe Browsing API integration, SSL validation, domain age checks
- **👁️ Preview Pages** - Branded preview pages with security badges before redirect
- **🎨 Customization** - Custom colors and logo embedding for QR codes
- **📱 Mobile Optimized** - Responsive design for all devices

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** SQLite (local) / PostgreSQL (production via Supabase)
- **Frontend:** HTML, CSS, JavaScript
- **Authentication:** JWT tokens
- **QR Generation:** qrcode + Pillow
- **Analytics:** Chart.js

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/qrsecure.git
   cd qrsecure
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run the server**
   ```bash
   cd backend
   python main.py
   ```

6. **Open in browser**
   ```
   http://localhost:8000
   ```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Your Supabase project URL | Optional* |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Optional* |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Safe Browsing API key | Optional |
| `APP_URL` | Your app's public URL | Yes |
| `SECRET_KEY` | Secret key for JWT tokens | Yes |
| `GEOLITE2_DB_PATH` | Path to GeoLite2 database | Optional |

*App works with SQLite locally if Supabase is not configured.

## Project Structure

```
qrsecure/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── database.py          # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py          # Authentication
│   │   ├── qr.py            # QR code CRUD
│   │   ├── analytics.py     # Analytics endpoints
│   │   └── redirect.py      # Redirect handling
│   └── services/
│       ├── qr_generator.py  # QR generation
│       ├── security.py      # Security checks
│       ├── analytics.py     # Scan logging
│       └── geolocation.py   # IP to location
├── frontend/
│   ├── index.html           # Landing page
│   ├── dashboard.html       # User dashboard
│   ├── login.html           # Login page
│   ├── signup.html          # Signup page
│   ├── css/styles.css       # Styles
│   └── js/
│       ├── auth.js          # Auth helper
│       └── dashboard.js     # Dashboard logic
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Create account
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user

### QR Codes
- `POST /api/qr/create` - Create QR code
- `GET /api/qr/list` - List user's QR codes
- `GET /api/qr/{code}` - Get QR details
- `PUT /api/qr/{code}` - Update destination
- `DELETE /api/qr/{code}` - Deactivate QR

### Analytics
- `GET /api/analytics/{code}` - Full analytics
- `GET /api/analytics/{code}/timeline` - Scans over time

### Redirect
- `GET /{code}` - Redirect (logs scan)
- `GET /preview/{code}` - Preview page

## Deployment

### Hugging Face Spaces

1. Create a new Space with Docker SDK
2. Upload all files
3. Add secrets in Space settings
4. Space will auto-build and deploy

### Render

1. Connect GitHub repository
2. Set environment variables
3. Deploy as Web Service

## License

MIT License - feel free to use for personal or commercial projects.

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

Built with ❤️ for secure QR codes
