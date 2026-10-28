import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
import requests
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database.database import get_db
from app.models.models import User

load_dotenv()
logger = logging.getLogger(__name__)

# Authentication Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-ai-meeting-key-replace-in-production-2025")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")) # 7 days

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


def hash_password(password: str) -> str:
    """Hash password securely using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token has expired.")
        return None
    except jwt.PyJWTError as e:
        logger.debug(f"Invalid token: {e}")
        return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """
    Extract token from Authorization: Bearer <token> header or
    'access_token' cookie.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.strip()
    return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Extract current user from token if present, returns None if not authenticated.
    Used for endpoints that support both authenticated users and guests.
    """
    if db is None:
        return None
    token = extract_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        return None
    try:
        return db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.warning(f"Error querying user {user_id}: {e}")
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency requiring valid authenticated user.
    Raises HTTP 401 if not authenticated.
    """
    user = get_optional_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ============================================================
# Google OAuth 2.0 Helpers
# ============================================================

def is_google_oauth_configured() -> bool:
    """Checks whether Google OAuth client ID and secret are configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Construct Google OAuth 2.0 authorization URL."""
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID environment variable is not configured.")
    
    scope = "openid email profile"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        "response_type=code&"
        f"scope={scope}&"
        "access_type=offline&"
        "prompt=consent"
    )
    if state:
        auth_url += f"&state={state}"
    return auth_url


def exchange_google_code(code: str) -> Dict[str, Any]:
    """Exchange authorization code with Google for tokens."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    res = requests.post(token_url, data=payload, timeout=10)
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth token exchange failed: {res.text}"
        )
    return res.json()


def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """Fetch user profile information using Google access token."""
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(userinfo_url, headers=headers, timeout=10)
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve Google user profile: {res.text}"
        )
    return res.json()
