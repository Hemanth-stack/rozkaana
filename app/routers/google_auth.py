import hashlib
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from redis.asyncio import Redis

from app.config import settings
from app.database import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_service import create_trial
from app.utils.redis_client import get_redis
from app.utils.security import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPES = "openid email profile"


@router.get("/google")
async def google_login(request: Request, redis: Redis = Depends(get_redis)):
    """Redirect user to Google OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    # Store state in Redis to prevent CSRF (10-min TTL)
    try:
        await redis.set(f"oauth_state:{state}", "1", ex=600)
    except Exception:
        pass  # degrade gracefully — state check in callback also degrades

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Handle Google OAuth callback, create/find user, redirect to frontend with JWT."""
    if error:
        logger.warning("Google OAuth error: %s", error)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?oauth_error={error}"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?oauth_error=missing_code"
        )

    # Validate state to prevent CSRF attacks
    if state:
        try:
            stored = await redis.get(f"oauth_state:{state}")
            await redis.delete(f"oauth_state:{state}")
            if not stored:
                logger.warning("OAuth callback: invalid or expired state token")
                return RedirectResponse(url=f"{settings.FRONTEND_URL}/?oauth_error=invalid_state")
        except Exception as e:
            logger.warning("OAuth state check failed (Redis unavailable): %s", e)

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()

            # Fetch user profile
            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_resp.raise_for_status()
            profile = user_resp.json()

    except Exception as exc:
        logger.error("Google token exchange failed: %s", exc)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?oauth_error=token_exchange_failed"
        )

    email = profile.get("email", "").lower().strip()
    name  = profile.get("name", "")
    picture = profile.get("picture", "")

    if not email:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?oauth_error=no_email"
        )

    # Get or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = user is None

    if is_new:
        phone_placeholder = "g" + hashlib.md5(email.encode()).hexdigest()[:13]
        user = User(
            phone=phone_placeholder,
            email=email,
            name=name,
            email_verified=True,
            onboarding_complete=False,
            is_admin=False,
            is_household_head=False,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("New user via Google OAuth: %s", email)
    else:
        # Update name/verified on returning users if missing
        if not user.name and name:
            user.name = name
        user.email_verified = True
        await db.flush()
        await db.refresh(user)
        logger.info("Existing user via Google OAuth: %s", email)

    # Ensure trial subscription for new users (onboarding_complete stays False
    # until the user finishes the onboarding form)
    if is_new:
        sub = (await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )).scalar_one_or_none()
        if not sub:
            await create_trial(user.id, "solo_pro", db)
            # Send welcome email
            try:
                from app.services.email_service import email_service
                from datetime import date, timedelta
                trial_end = str(date.today() + timedelta(days=7))
                await email_service.send_trial_start(email, name or "there", trial_end)
            except Exception:
                pass

    # Issue JWT
    data = {"sub": str(user.id)}
    access_token  = create_access_token(data)
    refresh_token = create_refresh_token(data)

    # Redirect to frontend success page with tokens in query params
    redirect_url = (
        f"{settings.FRONTEND_URL}/auth/success"
        f"?access_token={access_token}"
        f"&refresh_token={refresh_token}"
        f"&is_new={str(is_new).lower()}"
        f"&name={name.replace(' ', '%20')}"
    )
    return RedirectResponse(url=redirect_url)
