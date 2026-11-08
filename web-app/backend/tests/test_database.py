"""Connects to real PostgreSQL; all inserted fixtures roll back."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from vibicle_api.config import Settings
from vibicle_api.database import make_engine
from vibicle_api.repositories.database import DatabaseRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def engine() -> Engine:
    database = os.getenv("VIBICLE_TEST_DB")
    if not database:
        pytest.skip("Not Run: set VIBICLE_TEST_DB to a disposable migrated database")
    if not database.startswith("vibicle_3a_verify"):
        pytest.fail("Use a dedicated vibicle_3a_verify* database, not production")
    # The caller must supply its own actual DB password. No output includes it.
    settings = Settings(postgres_db=database)
    result = make_engine(settings)
    yield result
    result.dispose()


def test_real_connection_and_migrated_tables(engine: Engine) -> None:
    info = DatabaseRepository(engine).probe()
    assert info["encoding"] == "UTF8"
    assert set(inspect(engine).get_table_names()) == {
        "app_users",
        "auth_sessions",
        "auth_rate_limit_buckets",
        "vehicles",
        "vehicle_mileage_changes",
        "maintenance_events",
        "maintenance_record_versions",
        "vehicle_images",
        "alembic_version",
    }


def test_models_match_migration(engine: Engine) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from vibicle_api.models import Base

    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


@pytest.mark.parametrize(
    "email,password_hash",
    [
        ("Upper@example.com", "fixture"),
        (" spaced@example.com ", "fixture"),
        ("", "fixture"),
        ("x" * 255, "fixture"),
        ("test@example.com", ""),
    ],
)
def test_user_checks(engine: Engine, email: str, password_hash: str) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app_users(email,password_hash) VALUES (:e,:p)"),
            {"e": email, "p": password_hash},
        )


def test_email_unique(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        for _ in range(2):
            connection.execute(
                text("INSERT INTO app_users(email,password_hash) VALUES (:e,:p)"),
                {"e": "fixture@example.com", "p": "test-only-not-a-real-hash"},
            )


SESSION_BAD_CASES = [
    {"token_hash": b"x" * 31},
    {"csrf_secret": b"x" * 31},
    {"csrf_secret": None},
    {"kind": "other"},
    {"kind": "authenticated"},
    {"user_id": uuid4()},
    {"last_activity_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=1)},
    {"absolute_expires_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=16)},
    {"revoked_at": datetime(2025, 12, 31, tzinfo=UTC)},
]


def session_parameters() -> dict[str, object]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return dict(
        token_hash=os.urandom(32),
        csrf_secret=os.urandom(32),
        kind="preauth",
        user_id=None,
        created_at=start,
        last_activity_at=start,
        absolute_expires_at=start + timedelta(minutes=15),
        revoked_at=None,
    )


SESSION_INSERT = text("""
    INSERT INTO auth_sessions
    (token_hash,csrf_secret,kind,user_id,created_at,last_activity_at,absolute_expires_at,revoked_at)
    VALUES (:token_hash,:csrf_secret,:kind,:user_id,:created_at,:last_activity_at,
            :absolute_expires_at,:revoked_at)
""")


@pytest.mark.parametrize("changes", SESSION_BAD_CASES)
def test_session_checks(engine: Engine, changes: dict[str, object]) -> None:
    parameters = session_parameters() | changes
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(SESSION_INSERT, parameters)


def test_authenticated_fk_ttl_and_restrict(engine: Engine) -> None:
    # Roll back the whole fixture regardless of assertion outcomes.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            user = connection.execute(
                text(
                    "INSERT INTO app_users(email,password_hash)"
                    " VALUES ('fixture@example.com','fixture')"
                    " RETURNING id"
                )
            ).scalar_one()
            p = session_parameters()
            p.update(
                kind="authenticated",
                user_id=user,
                absolute_expires_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=8),
            )
            connection.execute(SESSION_INSERT, p)
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text("DELETE FROM app_users WHERE id=:id"), {"id": user})
            with pytest.raises(IntegrityError), connection.begin_nested():
                p["token_hash"] = os.urandom(32)
                p["absolute_expires_at"] = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=9)
                connection.execute(SESSION_INSERT, p)
            with pytest.raises(IntegrityError), connection.begin_nested():
                p["token_hash"] = os.urandom(32)
                p["user_id"] = uuid4()
                p["absolute_expires_at"] = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=8)
                connection.execute(SESSION_INSERT, p)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("scope", ["login", "register", "csrf_context"])
def test_preauth_and_bucket_valid(engine: Engine, scope: str) -> None:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(SESSION_INSERT, session_parameters())
            connection.execute(
                text("""
                INSERT INTO auth_rate_limit_buckets(scope,subject_hash,window_start,expires_at)
                VALUES (:scope,:hash,:start,:expiry)
            """),
                dict(
                    scope=scope,
                    hash=os.urandom(32),
                    start=datetime(2026, 1, 1, tzinfo=UTC),
                    expiry=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5),
                ),
            )
        finally:
            transaction.rollback()


@pytest.mark.parametrize(
    ("scope", "subject", "count", "duration"),
    [
        ("other", b"x" * 32, 1, 300),
        ("login", b"x" * 31, 1, 300),
        ("login", b"x" * 32, 0, 300),
        ("login", b"x" * 32, 1, 0),
    ],
)
def test_bucket_checks(
    engine: Engine,
    scope: str,
    subject: bytes,
    count: int,
    duration: int,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO auth_rate_limit_buckets
            (scope,subject_hash,window_start,attempt_count,expires_at)
            VALUES (:scope,:hash,:start,:count,:expiry)
        """),
            dict(
                scope=scope,
                hash=subject,
                start=start,
                count=count,
                expiry=start + timedelta(seconds=duration),
            ),
        )


def test_bucket_composite_primary_key(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        for _ in range(2):
            connection.execute(
                text("""
                INSERT INTO auth_rate_limit_buckets(scope,subject_hash,window_start,expires_at)
                VALUES ('login',:hash,'2026-01-01T00:00Z','2026-01-01T00:05Z')
            """),
                {"hash": b"x" * 32},
            )


def test_real_connection_failure_is_not_empty_data() -> None:
    bad = make_engine(Settings(postgres_port=1))
    try:
        with pytest.raises(OperationalError):
            DatabaseRepository(bad).probe()
    finally:
        bad.dispose()
