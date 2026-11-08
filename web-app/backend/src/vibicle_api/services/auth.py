from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from secrets import token_bytes
from threading import BoundedSemaphore
from typing import Literal
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from vibicle_api.errors import ContractError, reject
from vibicle_api.models import AppUser, AuthSession
from vibicle_api.repositories.auth import clock, context, hit_rate_gate, subject_key
from vibicle_api.schemas import (
    Credentials,
    CsrfData,
    CurrentUser,
    ErrorData,
    IdentityData,
    LoginData,
    Registration,
    SessionMeta,
)
from vibicle_api.services.identity import (
    PREAUTH_TTL,
    SESSION_TTL,
    active,
    context_kind,
    encode_token,
    verify_csrf,
)

PASSWORDS = PasswordHash((Argon2Hasher(memory_cost=19456, time_cost=2, parallelism=1),))
DUMMY_HASH = PASSWORDS.hash(encode_token(token_bytes(32)))
KDF_SLOT = BoundedSemaphore(1)
RATE_POLICY = {"csrf_context": (60, 300), "register": (10, 3600), "login": (20, 300)}


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    session_hash: bytes


@contextmanager
def password_slot() -> Iterator[None]:
    if not KDF_SLOT.acquire(blocking=False):
        reject(503, "AUTH_BUSY", "登入服務忙碌，請稍後再試。")
    try:
        yield
    finally:
        KDF_SLOT.release()


def normalized_email(value: str) -> str:
    try:
        return validate_email(
            value.strip(), check_deliverability=False, test_environment=True
        ).normalized
    except EmailNotValidError:
        reject(422, "VALIDATION_FAILED", "請輸入有效的 Email。", field="email")


def commit(db: Session) -> None:
    db.flush()
    try:
        db.commit()
    except IntegrityError:
        raise
    except DBAPIError as exc:
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if (
            exc.connection_invalidated
            or sqlstate in {"08007", "40003"}
            or (isinstance(exc, OperationalError) and sqlstate is None)
        ):
            raise ContractError(
                503,
                ErrorData(
                    code="COMMIT_OUTCOME_UNKNOWN",
                    outcome="unknown",
                    message="無法確認儲存結果，請先核對目前狀態。",
                ),
            ) from None
        raise


class AuthService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def rate_gate(self, scope: str, address: str, secret: bytes) -> None:
        try:
            subject = subject_key(address, secret)
        except ValueError:
            reject(403, "SOURCE_NOT_ALLOWED", "無法辨識來源。")
        limit, seconds = RATE_POLICY[scope]
        with Session(self.engine) as db:
            count, remaining = hit_rate_gate(db, scope, subject, seconds, limit)
            commit(db)
        if count > limit:
            reject(
                429,
                "RATE_LIMITED",
                "請稍後再試。",
                retry_after=max(1, ceil(remaining.total_seconds())),
            )

    @staticmethod
    def new_context(
        db: Session, kind: Literal["preauth", "authenticated"], user_id: UUID | None
    ) -> tuple[str, AuthSession]:
        raw = token_bytes(32)
        now = clock(db)
        row = AuthSession(
            token_hash=sha256(raw).digest(),
            csrf_secret=token_bytes(32),
            kind=kind,
            user_id=user_id,
            created_at=now,
            last_activity_at=now,
            absolute_expires_at=now + (PREAUTH_TTL if kind == "preauth" else SESSION_TTL),
        )
        db.add(row)
        return encode_token(raw), row

    def bootstrap(self, token: bytes | None) -> tuple[CsrfData, str | None]:
        with Session(self.engine, expire_on_commit=False) as db:
            found = context(db, token) if token is not None else None
            raw = None
            if found is not None and active(*found):
                row = found[0]
            else:
                raw, row = self.new_context(db, "preauth", None)
                commit(db)
            return CsrfData(
                context_type=context_kind(row),
                csrf_token=encode_token(row.csrf_secret),
                absolute_expires_at=row.absolute_expires_at,
            ), raw

    def check_context(
        self, token: bytes | None, csrf: bytes | None, *, preauth: bool = False
    ) -> bytes:
        if token is None:
            reject(403, "CSRF_CONTEXT_REQUIRED", "請先取得安全驗證。")
        with Session(self.engine) as db:
            found = context(db, token)
            if found is None or not active(*found):
                reject(403, "CSRF_CONTEXT_REQUIRED", "安全驗證已失效。")
            verify_csrf(found[0], csrf)
            if preauth and found[0].kind != "preauth":
                reject(403, "OPERATION_NOT_ALLOWED", "請先登出再註冊。")
        return token

    def register(self, token: bytes, csrf: bytes | None, credentials: Registration) -> None:
        email = normalized_email(credentials.email)
        if credentials.password != credentials.password_confirmation:
            reject(
                422,
                "PASSWORD_CONFIRMATION_MISMATCH",
                "兩次輸入的密碼不同。",
                field="password_confirmation",
            )
        with password_slot():
            hashed = PASSWORDS.hash(credentials.password)
        try:
            with Session(self.engine) as db:
                found = context(db, token, locked=True)
                if found is None or not active(*found) or found[0].kind != "preauth":
                    reject(403, "CSRF_CONTEXT_REQUIRED", "安全驗證已失效。")
                verify_csrf(found[0], csrf)
                canonical: str = db.execute(select(func.lower(email))).scalar_one()
                if not 1 <= len(canonical) <= 254:
                    reject(422, "VALIDATION_FAILED", "Email 長度不合規。", field="email")
                db.add(AppUser(email=canonical, password_hash=hashed))
                commit(db)
        except IntegrityError as exc:
            if (
                getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "uq_app_users_email"
            ):
                reject(409, "REGISTRATION_CONFLICT", "無法建立此帳號。")
            raise

    def login(
        self, token: bytes, csrf: bytes | None, credentials: Credentials
    ) -> tuple[LoginData, str]:
        email = normalized_email(credentials.email)
        with Session(self.engine) as db:
            user = db.scalar(select(AppUser).where(AppUser.email == func.lower(email)))
        with password_slot():
            verified = PASSWORDS.verify(
                credentials.password, user.password_hash if user else DUMMY_HASH
            )
        if not verified or user is None:
            reject(401, "INVALID_CREDENTIALS", "Email 或密碼不正確。")
        with Session(self.engine, expire_on_commit=False) as db:
            found = context(db, token, locked=True)
            if found is None or not active(*found):
                reject(409, "AUTH_CONTEXT_CHANGED", "登入狀態已變更，請重新確認。")
            old, now = found
            verify_csrf(old, csrf)
            raw, row = self.new_context(db, "authenticated", user.id)
            old.revoked_at = now
            commit(db)
            return LoginData(
                user=CurrentUser(id=user.id, email=user.email),
                csrf_token=encode_token(row.csrf_secret),
                absolute_expires_at=row.absolute_expires_at,
            ), raw

    def logout(self, token: bytes | None, csrf: bytes | None) -> None:
        if token is None:
            reject(403, "CSRF_CONTEXT_REQUIRED", "無法驗證要撤銷的登入狀態。")
        with Session(self.engine) as db:
            found = context(db, token, locked=True)
            if found is None:
                reject(403, "CSRF_CONTEXT_REQUIRED", "無法驗證要撤銷的登入狀態。")
            row, now = found
            if row.kind == "preauth" and now >= row.absolute_expires_at:
                reject(403, "CSRF_CONTEXT_REQUIRED", "安全驗證已失效。")
            verify_csrf(row, csrf)
            if row.revoked_at is None:
                row.revoked_at = now
            commit(db)

    def current_user(self, token: bytes | None) -> IdentityData:
        if token is None:
            return IdentityData()
        with Session(self.engine) as db:
            result = db.execute(
                select(AppUser.id, AppUser.email, AuthSession.absolute_expires_at)
                .join(AuthSession, AuthSession.user_id == AppUser.id)
                .where(
                    AuthSession.token_hash == token,
                    AuthSession.kind == "authenticated",
                    AuthSession.revoked_at.is_(None),
                    func.statement_timestamp() < AuthSession.absolute_expires_at,
                    func.statement_timestamp()
                    < AuthSession.last_activity_at + text("INTERVAL '30 minutes'"),
                )
            ).one_or_none()
            if result is None:
                return IdentityData()
            return IdentityData(
                authenticated=True,
                user=CurrentUser(id=result.id, email=result.email),
                absolute_expires_at=result.absolute_expires_at,
            )

    def authorize(
        self, token: bytes | None, csrf: bytes | None = None, *, mutation: bool = False
    ) -> Identity:
        if token is None:
            reject(401, "AUTHENTICATION_REQUIRED", "請先登入。")
        with Session(self.engine) as db:
            found = context(db, token)
            if found is None or not active(*found) or found[0].user_id is None:
                reject(401, "AUTHENTICATION_REQUIRED", "請先登入。")
            row = found[0]
            if mutation:
                verify_csrf(row, csrf)
            assert row.user_id is not None
            return Identity(row.user_id, token)

    def touch(self, token: bytes) -> SessionMeta:
        try:
            with Session(self.engine) as db:
                found = context(db, token, locked=True)
                if found is None:
                    return SessionMeta(
                        activity="not_extended",
                        requires_revalidation=True,
                        reason="SESSION_EXPIRED",
                    )
                row, now = found
                if row.revoked_at is not None:
                    return SessionMeta(
                        activity="not_extended",
                        requires_revalidation=True,
                        reason="SESSION_REVOKED",
                    )
                if row.kind != "authenticated" or not active(row, now):
                    return SessionMeta(
                        activity="not_extended",
                        requires_revalidation=True,
                        reason="SESSION_EXPIRED",
                    )
                row.last_activity_at = max(row.last_activity_at, now)
                db.commit()
                return SessionMeta(activity="touched")
        except SQLAlchemyError:
            return SessionMeta(
                activity="unknown", requires_revalidation=True, reason="SESSION_STORE_UNAVAILABLE"
            )
