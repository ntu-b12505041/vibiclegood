from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from re import fullmatch
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Request, Response

from vibicle_api.errors import reject
from vibicle_api.http_contract import one_header
from vibicle_api.models import AuthSession

SESSION_COOKIE = "__Host-vibicle_session"
PREAUTH_TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(hours=8)
IDLE_TTL = timedelta(minutes=30)


def encode_token(raw: bytes) -> str:
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_token(value: str | None) -> bytes | None:
    if value is None or not fullmatch(r"[A-Za-z0-9_-]{43}", value):
        return None
    raw = urlsafe_b64decode(value + "=")
    return raw if encode_token(raw) == value else None


def cookie_hash(request: Request) -> bytes | None:
    values: list[str] = []
    for header in request.headers.getlist("cookie"):
        for pair in header.split(";"):
            name, separator, value = pair.strip().partition("=")
            if name.strip() == SESSION_COOKIE:
                values.append(value if separator else "")
    if len(values) > 1:
        reject(400, "AMBIGUOUS_COOKIE", "Session Cookie 重複，無法判讀。")
    token = decode_token(values[0] if values else None)
    return sha256(token).digest() if token is not None else None


def set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def context_kind(row: AuthSession) -> Literal["authenticated", "preauth"]:
    return "authenticated" if row.kind == "authenticated" else "preauth"


def active(row: AuthSession, now: datetime) -> bool:
    return (
        row.revoked_at is None
        and now < row.absolute_expires_at
        and (row.kind == "preauth" or now < row.last_activity_at + IDLE_TTL)
    )


def verify_csrf(row: AuthSession, token: bytes | None) -> None:
    if token is None or not compare_digest(row.csrf_secret, token):
        reject(403, "CSRF_INVALID", "安全驗證已失效，請重新確認登入狀態。")


def source_origin(value: str, *, referer: bool) -> tuple[str, str, int] | None:
    if any(ord(char) <= 32 or ord(char) == 127 or char in "\\," for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "http"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or (not referer and (parsed.path or parsed.query or "?" in value or "#" in value))
        ):
            return None
        port = parsed.port
        if port == 0:
            return None
        return parsed.scheme, parsed.hostname, port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None


def verify_source(request: Request, expected_origin: str) -> None:
    origin = one_header(request, "origin")
    referer = one_header(request, "referer")
    fetch_site = one_header(request, "sec-fetch-site")
    expected = source_origin(expected_origin, referer=False)
    actual = source_origin(origin if origin is not None else referer or "", referer=origin is None)
    if expected is None or actual != expected or fetch_site not in (None, "same-origin"):
        reject(403, "SOURCE_NOT_ALLOWED", "請從本網站發出請求。")
