import base64
import hashlib
import hmac
import json
import time
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str, secret: str) -> dict:
    """Verify and decode an HS256 JWT using only the standard library."""
    try:
        header_part, payload_part, signature_part = token.split(".")

        def decode_part(part: str) -> bytes:
            return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))

        header = json.loads(decode_part(header_part))
        payload = json.loads(decode_part(payload_part))
        if not isinstance(header, dict) or header.get("alg") != "HS256":
            raise ValueError("Unsupported JWT algorithm")
        if not isinstance(payload, dict):
            raise ValueError("Invalid JWT payload")

        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        signature = decode_part(signature_part)
        expected = hmac.new(secret.encode("utf-8"), signing_input,
                            hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid JWT signature")

        now = time.time()
        if "exp" in payload and float(payload["exp"]) <= now:
            raise ValueError("Expired JWT")
        if "nbf" in payload and float(payload["nbf"]) > now:
            raise ValueError("JWT not yet valid")
        return payload
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JWT") from exc


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if creds is None:
        raise unauthorized
    try:
        payload = _decode_token(creds.credentials, settings.secret_key)
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: Role):
    """Use as a route dependency: only the listed roles get through."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "You do not have access")
        return user
    return checker
