import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import storage
from models import Credentials, TokenResponse

DEFAULT_JWT_SECRET = "change-me"
JWT_SECRET = os.environ.get("JWT_SECRET", DEFAULT_JWT_SECRET)
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "120"))
APP_ENV = os.environ.get("APP_ENV", "development")

bearer = HTTPBearer()


def validate_jwt_secret_on_startup():
    if APP_ENV == "production" and JWT_SECRET == DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is still the default 'change-me' value with APP_ENV=production. "
            "Set a real secret (see charts/k8s-troubleshooter/templates/secret.yaml) before starting."
        )


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def register(creds: Credentials) -> TokenResponse:
    if storage.get_user(creds.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user_id = storage.create_user(creds.username, _hash(creds.password))
    return _issue(user_id, creds.username)


def login(creds: Credentials) -> TokenResponse:
    user = storage.get_user(creds.username)
    if not user or not _verify(creds.password, user["password_hash"]):
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
