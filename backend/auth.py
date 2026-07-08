import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import storage
from models import Credentials, TokenResponse

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "120"))

bearer = HTTPBearer()


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def register(creds: Credentials) -> TokenResponse:
    if storage.get_user(creds.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    salt = secrets.token_hex(16)
    user_id = storage.create_user(creds.username, _hash(creds.password, salt), salt)
    return _issue(user_id, creds.username)


def login(creds: Credentials) -> TokenResponse:
    user = storage.get_user(creds.username)
    if not user or _hash(creds.password, user["salt"]) != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _issue(user["id"], user["username"])


def _issue(user_id: int, username: str) -> TokenResponse:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return TokenResponse(access_token=jwt.encode(payload, JWT_SECRET, algorithm="HS256"))


def current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
