from datetime import datetime, timedelta
from hashlib import sha256
from hmac import digest
from ipaddress import IPv6Address, ip_address

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vibicle_api.models import AuthSession

RATE_GATE = text("""
WITH moment AS (SELECT statement_timestamp() AS ts),
     bounds AS (
       SELECT ts, to_timestamp(floor(extract(epoch FROM ts) / :seconds) * :seconds) AS start
       FROM moment
     )
INSERT INTO auth_rate_limit_buckets (scope, subject_hash, window_start, attempt_count, expires_at)
SELECT :scope, :subject, start, 1, start + make_interval(secs => :seconds) FROM bounds
ON CONFLICT (scope, subject_hash, window_start) DO UPDATE
SET attempt_count = least(auth_rate_limit_buckets.attempt_count + 1, :cap)
RETURNING attempt_count, expires_at - (SELECT ts FROM moment) AS remaining
""")


def subject_key(address: str, secret: bytes) -> bytes:
    ip = ip_address(address)
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return digest(secret, str(ip).encode("ascii"), sha256)


def clock(db: Session) -> datetime:
    value: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return value


def context(
    db: Session, token: bytes, *, locked: bool = False
) -> tuple[AuthSession, datetime] | None:
    if locked:
        row = db.get(AuthSession, token, with_for_update=True)
        return (row, clock(db)) if row else None
    result = db.execute(
        select(AuthSession, func.statement_timestamp()).where(AuthSession.token_hash == token)
    ).one_or_none()
    return (result[0], result[1]) if result else None


def hit_rate_gate(
    db: Session, scope: str, subject: bytes, seconds: int, limit: int
) -> tuple[int, timedelta]:
    row = db.execute(
        RATE_GATE, {"scope": scope, "subject": subject, "seconds": seconds, "cap": limit + 1}
    ).one()
    return row[0], row[1]
