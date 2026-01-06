"""
QRSecure Authentication Routes
Handles user registration, login, and session management.
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
from jose import JWTError, jwt

from database import get_db
from models import User
from config import get_settings

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Bearer token security
security = HTTPBearer(auto_error=False)


# Request/Response Models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    user_id: str
    email: str
    created_at: datetime
    subscription_tier: str


# Helper Functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # Truncate password to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Create a JWT access token."""
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.utcnow() + expires_delta
    
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get the current authenticated user.
    Returns None if not authenticated (for optional auth).
    """
    if not credentials:
        return None
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        result = await db.execute(select(User).filter(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        return user
    except JWTError:
        return None


async def require_auth(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


# Routes
@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignUpRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account.
    """
    try:
        # Check if email already exists
        result = await db.execute(select(User).filter(User.email == request.email))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Validate password
        if len(request.password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters"
            )
        
        # Hash password
        try:
            hashed = hash_password(request.password)
        except Exception as hash_error:
            print(f"Password hashing error: {hash_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Password hashing failed: {str(hash_error)}"
            )
        
        # Create user
        user = User(
            email=request.email,
            password_hash=hashed,
            subscription_tier="free"
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Generate token
        token, expires_in = create_access_token(user.user_id, user.email)
        
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            user={
                "user_id": user.user_id,
                "email": user.email,
                "subscription_tier": user.subscription_tier
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Signup failed: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Log in an existing user.
    """
    # Find user
    result = await db.execute(select(User).filter(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is deactivated"
        )
    
    # Generate token
    token, expires_in = create_access_token(user.user_id, user.email)
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "user_id": user.user_id,
            "email": user.email,
            "subscription_tier": user.subscription_tier
        }
    )


@router.post("/logout")
async def logout():
    """
    Log out the current user.
    Note: With JWT, logout is handled client-side by removing the token.
    This endpoint exists for completeness and can be used for token blacklisting.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_auth)):
    """
    Get current user information.
    """
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        created_at=user.created_at,
        subscription_tier=user.subscription_tier
    )


@router.get("/verify")
async def verify_token(user: Optional[User] = Depends(get_current_user)):
    """
    Verify if the current token is valid.
    """
    if user:
        return {
            "valid": True,
            "user_id": user.user_id,
            "email": user.email
        }
    return {"valid": False}
