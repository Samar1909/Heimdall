import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, Union

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from dotenv import load_dotenv
from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

import models
from database import get_db
from redis_server import r as redis_client

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(64)
    print("WARNING: JWT_SECRET_KEY not set - using an ephemeral key. Set JWT_SECRET_KEY in production.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"

_hasher = PasswordHasher()

db_dependency = Annotated[Session, Depends(get_db)]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def _create_token(payload: dict, expires_delta: timedelta) -> str:
    to_encode = payload.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(account_id: str, role: str = "account") -> str:
    return _create_token({"sub": account_id, "type": "access", "role": role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(account_id: str, jti: str, role: str = "account") -> str:
    return _create_token({"sub": account_id, "type": "refresh", "jti": jti, "role": role}, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def issue_auth_cookies(response: Response, account_id: str, role: str = "account") -> None:
    """Issue access, refresh and CSRF cookies for an authenticated session.

    access_token/refresh_token are httpOnly so JS can't read them; csrf_token
    is intentionally readable so the client can echo it back in the
    X-CSRF-Token header (double-submit cookie pattern).
    """
    csrf_token = secrets.token_urlsafe(32)
    refresh_jti = secrets.token_urlsafe(16)

    access_token = create_access_token(account_id, role)
    refresh_token = create_refresh_token(account_id, refresh_jti, role)

    redis_client.setex(f"refresh:{refresh_jti}", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), account_id)

    response.set_cookie(
        ACCESS_COOKIE_NAME, access_token, httponly=True, secure=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME, refresh_token, httponly=True, secure=True, samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600, path="/auth",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME, csrf_token, httponly=False, secure=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def revoke_refresh_token(refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except HTTPException:
        return
    jti = payload.get("jti")
    if jti:
        redis_client.delete(f"refresh:{jti}")


def get_current_account(
    db: db_dependency,
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> models.Account:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(access_token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    account = db.query(models.Account).filter(models.Account.id == payload["sub"]).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    return account


current_account_dependency = Annotated[models.Account, Depends(get_current_account)]


def get_current_user(
    db: db_dependency,
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> models.User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(access_token)
    if payload.get("type") != "access" or payload.get("role") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = db.query(models.User).filter(models.User.user_id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


current_user_dependency = Annotated[models.User, Depends(get_current_user)]


def get_current_merchant(
    db: db_dependency,
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> models.Merchant:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(access_token)
    if payload.get("type") != "access" or payload.get("role") != "merchant":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    merchant = db.query(models.Merchant).filter(models.Merchant.merchant_id == int(payload["sub"])).first()
    if not merchant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Merchant not found")
    return merchant


current_merchant_dependency = Annotated[models.Merchant, Depends(get_current_merchant)]


def verify_csrf(
    csrf_token: Annotated[Optional[str], Cookie()] = None,
    x_csrf_token: Annotated[Optional[str], Header()] = None,
) -> None:
    """Double-submit cookie CSRF check for state-changing requests."""
    if not csrf_token or not x_csrf_token or not secrets.compare_digest(csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def _resolve_entity_from_token(db: Session, access_token: Optional[str]) -> Union[models.User, models.Merchant]:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(access_token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    role = payload.get("role")
    if role == "user":
        entity = db.query(models.User).filter(models.User.user_id == int(payload["sub"])).first()
    elif role == "merchant":
        entity = db.query(models.Merchant).filter(models.Merchant.merchant_id == int(payload["sub"])).first()
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token role")

    if not entity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    return entity


def get_current_entity(
    db: db_dependency,
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> Union[models.User, models.Merchant]:
    """JWT check only (user or merchant), for read-only routes either can call."""
    return _resolve_entity_from_token(db, access_token)


current_entity_dependency = Annotated[Union[models.User, models.Merchant], Depends(get_current_entity)]


def require_auth_and_csrf(
    db: db_dependency,
    access_token: Annotated[Optional[str], Cookie()] = None,
    _: Annotated[None, Depends(verify_csrf)] = None,
) -> Union[models.User, models.Merchant]:
    """JWT (user or merchant) + CSRF check combined, for state-changing routes either can call."""
    return _resolve_entity_from_token(db, access_token)


protected_route = Annotated[Union[models.User, models.Merchant], Depends(require_auth_and_csrf)]
