import os
import re
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import User
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
    is_google_oauth_configured,
    get_google_auth_url,
    exchange_google_code,
    get_google_user_info,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================
# Request / Response Schemas
# ============================================================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric username")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Secure password")
    full_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=3, description="Username or email address")
    password: str = Field(..., min_length=1, description="Password")


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    google_connected: bool = False
    google_email: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


# ============================================================
# Auth Endpoints
# ============================================================

@auth_router.post("/register")
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Register a new user account with secure password hashing and validation."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    clean_username = req.username.strip().lower()
    clean_email = req.email.strip().lower()

    # Validate username syntax (alphanumeric + underscore/hyphen)
    if not re.match(r"^[a-zA-Z0-9_\-]+$", clean_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username may only contain letters, numbers, underscores, and hyphens."
        )

    # Check for existing username or email
    existing_user = db.query(User).filter(
        (User.username == clean_username) | (User.email == clean_email)
    ).first()

    if existing_user:
        if existing_user.username == clean_username:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken.")
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    new_user = User(
        id=str(uuid.uuid4()),
        username=clean_username,
        email=clean_email,
        full_name=req.full_name.strip() if req.full_name else None,
        password_hash=hash_password(req.password),
        google_connected=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": new_user.id, "username": new_user.username, "email": new_user.email})

    # Registration must not automatically authenticate the session; user must log in.
    response.delete_cookie(key="access_token", path="/")

    return {
        "success": True,
        "message": "Account created successfully. Please sign in with your credentials.",
        "token": token,
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "google_connected": False,
        }
    }


@auth_router.post("/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user with username/email and password, issuing a JWT session."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    identifier = req.username_or_email.strip().lower()
    user = db.query(User).filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password."
        )

    token = create_access_token({"sub": user.id, "username": user.username, "email": user.email})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600
    )

    return {
        "success": True,
        "message": "Logged in successfully.",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "google_connected": bool(user.google_connected),
            "google_email": user.google_email,
        }
    }


@auth_router.post("/logout")
def logout(response: Response):
    """End the user session by clearing the access token cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"success": True, "message": "Logged out successfully."}


@auth_router.get("/logout")
def logout_get(response: Response):
    """End the user session via GET navigation and redirect to login."""
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="access_token", path="/")
    return resp


@auth_router.get("/me")
def get_profile(current_user: Optional[User] = Depends(get_optional_user)):
    """Return the currently authenticated user's profile and Google connection state."""
    if not current_user:
        return {
            "authenticated": False,
            "user": None
        }

    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "google_connected": bool(current_user.google_connected),
            "google_email": current_user.google_email,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        }
    }


# ============================================================
# Google Account Connection Endpoints
# ============================================================

@auth_router.get("/google/status")
def google_status(current_user: Optional[User] = Depends(get_optional_user)):
    """Returns Google OAuth configuration status and user's Google connection state."""
    is_configured = is_google_oauth_configured()
    is_connected = bool(current_user and current_user.google_connected)
    google_email = current_user.google_email if current_user else None
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    return {
        "configured": is_configured,
        "connected": is_connected,
        "google_email": google_email,
        "redirect_uri": redirect_uri,
        "notice": "Google OAuth is ready to connect." if is_configured else "Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) not yet configured in .env.",
        "setup_guide": None if is_configured else {
            "title": "Google Cloud OAuth Setup Required",
            "redirect_uri": redirect_uri,
            "steps": [
                "Open Google Cloud Console -> APIs & Services -> Credentials.",
                "Create an OAuth 2.0 Client ID (Application type: Web application).",
                f"Set Authorized redirect URI to: {redirect_uri}",
                "Copy Client ID and Client Secret into your .env file as GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
                "Restart the server."
            ],
            "browser_signin_alternative": "You can also click 'Open Browser to Sign In' to authenticate Chrome directly without OAuth credentials."
        }
    }


@auth_router.get("/google/url")
def google_auth_url(current_user: Optional[User] = Depends(get_optional_user)):
    """Generate the Google OAuth 2.0 authorization redirect URL."""
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    if not is_google_oauth_configured():
        return {
            "success": False,
            "configured": False,
            "message": "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
            "setup_guide": {
                "title": "Google Cloud OAuth Setup Required",
                "redirect_uri": redirect_uri,
                "steps": [
                    "Open Google Cloud Console -> APIs & Services -> Credentials.",
                    "Create an OAuth 2.0 Client ID (Application type: Web application).",
                    f"Set Authorized redirect URI to: {redirect_uri}",
                    "Copy Client ID and Client Secret into your .env file as GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
                    "Restart the application server."
                ],
                "browser_signin_alternative": "You can also click 'Open Browser to Sign In' to authenticate Chrome directly without OAuth credentials."
            }
        }
    try:
        state = current_user.id if current_user else None
        url = get_google_auth_url(state=state)
        return {"success": True, "configured": True, "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@auth_router.get("/google/callback")
def google_callback(code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle Google OAuth 2.0 callback, exchange tokens, and link to user account.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    if not is_google_oauth_configured():
        raise HTTPException(status_code=400, detail="Google OAuth is not configured.")

    try:
        tokens = exchange_google_code(code)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        google_user = get_google_user_info(access_token)

        google_sub = google_user.get("sub")
        google_email = google_user.get("email")
        google_name = google_user.get("name")

        # 1. If state parameter has user_id, link to that specific user
        user = None
        if state:
            user = db.query(User).filter(User.id == state).first()

        # 2. Otherwise find by google_sub or email
        if not user and google_sub:
            user = db.query(User).filter(User.google_sub == google_sub).first()

        if not user and google_email:
            user = db.query(User).filter(User.email == google_email).first()

        # 3. If still no user exists, create one from Google profile
        if not user:
            base_username = (google_email.split("@")[0] if google_email else f"user_{uuid.uuid4().hex[:6]}")
            # Ensure unique username
            clean_username = re.sub(r"[^a-zA-Z0-9_\-]", "_", base_username).lower()
            if db.query(User).filter(User.username == clean_username).first():
                clean_username = f"{clean_username}_{uuid.uuid4().hex[:4]}"

            user = User(
                id=str(uuid.uuid4()),
                username=clean_username,
                email=google_email,
                full_name=google_name,
                password_hash=hash_password(uuid.uuid4().hex), # Random unguessable password
                google_connected=True,
                google_sub=google_sub,
                google_email=google_email,
                google_access_token=access_token,
                google_refresh_token=refresh_token
            )
            db.add(user)
        else:
            # Update existing user's Google connection
            user.google_connected = True
            user.google_sub = google_sub
            user.google_email = google_email
            user.google_access_token = access_token
            if refresh_token:
                user.google_refresh_token = refresh_token

        db.commit()
        db.refresh(user)

        # Create session token and redirect to dashboard
        token = create_access_token({"sub": user.id, "username": user.username, "email": user.email})
        response = RedirectResponse(url="/?google_connected=success", status_code=303)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 3600
        )
        return response

    except Exception as e:
        logger.exception(f"Google OAuth callback error: {e}")
        return RedirectResponse(url=f"/?google_error={str(e)}", status_code=303)


@auth_router.post("/google/disconnect")
def google_disconnect(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Disconnect user's connected Google account and clear stored credentials."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    current_user.google_connected = False
    current_user.google_access_token = None
    current_user.google_refresh_token = None
    current_user.google_email = None
    current_user.google_sub = None
    db.commit()

    return {
        "success": True,
        "message": "Google account disconnected successfully."
    }


# ============================================================
# Password Reset Endpoints
# ============================================================

@auth_router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Handle password reset request. In local development or when SMTP is not configured,
    provides instructions and does not leak whether email exists.
    """
    if db:
        user = db.query(User).filter(User.email == req.email.strip().lower()).first()
        if user:
            # Generate a temporary reset token
            reset_token = create_access_token({"sub": user.id, "purpose": "pwd_reset"})
            logger.info(f"Password reset token generated for {user.email}: {reset_token[:12]}...")

    return {
        "success": True,
        "message": "If that email address is registered, password reset instructions have been dispatched."
    }


@auth_router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a valid reset token."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    from app.services.auth_service import decode_access_token
    payload = decode_access_token(req.token)
    if not payload or payload.get("purpose") != "pwd_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.password_hash = hash_password(req.new_password)
    db.commit()

    return {"success": True, "message": "Password has been successfully updated. You may now log in."}
