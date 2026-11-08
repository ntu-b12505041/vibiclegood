import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine

if not (Path(__file__).resolve().parents[2] / ".env").exists():
    os.environ.setdefault("POSTGRES_PASSWORD", "unit-test-placeholder-not-a-real-secret")


@pytest.fixture
def auth_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    database = os.getenv("VIBICLE_TEST_DB", "")
    if not database:
        pytest.skip("Requires a migrated verification DB")
    if not database.startswith("vibicle_3a_verify_"):
        pytest.fail("Use a dedicated vibicle_3a_verify_ database")
    monkeypatch.setenv("RATE_LIMIT_SECRET", uuid4().hex)
    monkeypatch.setenv("PUBLIC_ORIGIN", "https://vibicle.localhost:8443")
    get_settings.cache_clear()
    engine = make_engine(get_settings().model_copy(update={"postgres_db": database}))
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()
