import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ax-compass-agent-secret-2024")
ALGORITHM = "HS256"
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

USERS: dict[str, str] = {
    os.getenv("ADMIN_USERNAME", "admin"): os.getenv("ADMIN_PASSWORD", "ax2024"),
}

_bearer = HTTPBearer()


def authenticate(username: str, password: str) -> bool:
    return USERS.get(username) == password


def create_token(username: str, expires: Optional[timedelta] = None) -> str:
    exp = datetime.now(timezone.utc) + (expires or timedelta(hours=EXPIRE_HOURS))
    return jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
