from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine
from vibicle_api.main import app, create_app

client = TestClient(app)


def test_anonymous_contract_does_not_query_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_database(*args: object, **kwargs: object) -> None:
        pytest.fail("Anonymous E05 must not create/use a database connection")

    monkeypatch.setattr("vibicle_api.database.make_engine", no_database)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    UUID(body["meta"]["request_id"])
    assert body == {
        "data": {"authenticated": False, "user": None, "absolute_expires_at": None},
        "meta": {
            "request_id": response.headers["x-request-id"],
            "business_outcome": "read_only",
            "session": {
                "activity": "not_applicable",
                "requires_revalidation": False,
                "reason": None,
            },
        },
    }
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("cookie", ["forged-user-id", "", "A" * 42, "!" * 43, "B" * 43])
def test_invalid_cookie_never_authenticates(cookie: str) -> None:
    response = client.get("/api/auth/me", headers={"cookie": "__Host-vibicle_session=" + cookie})
    assert response.status_code == 200
    assert response.json()["data"]["authenticated"] is False
    assert "set-cookie" not in response.headers


def test_well_formed_cookie_fails_closed_when_postgres_is_unavailable() -> None:
    engine = make_engine(get_settings().model_copy(update={"postgres_port": 1}))
    with TestClient(create_app(engine)) as unavailable:
        response = unavailable.get(
            "/api/auth/me", headers={"cookie": "__Host-vibicle_session=" + "A" * 43}
        )
    engine.dispose()
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "STORE_UNAVAILABLE"
    assert body["meta"]["session"]["requires_revalidation"] is True
    assert "data" not in body
    assert "business_outcome" not in body["meta"]
    assert "set-cookie" not in response.headers


def test_duplicate_cookie_is_ambiguous() -> None:
    response = client.get(
        "/api/auth/me",
        headers={
            "cookie": "__Host-vibicle_session=a; __Host-vibicle_session=b",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AMBIGUOUS_COOKIE"


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/auth/me?user_id=forged", 422),
        ("/api/auth/me?a=1&a=2", 400),
    ],
)
def test_query_is_rejected(path: str, status: int) -> None:
    response = client.get(path)
    assert response.status_code == status
    assert "input" not in response.text


@pytest.mark.parametrize(("body", "status"), [(b"{}", 422), (b"x" * 8193, 413)])
def test_get_body_is_rejected(body: bytes, status: int) -> None:
    assert client.request("GET", "/api/auth/me", content=body).status_code == status


def test_diagnostics_not_exposed() -> None:
    assert client.get("/api/dev/db").status_code == 404
    assert client.post("/api/auth/me").status_code == 405


def test_store_failure_is_not_empty_public_data_or_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_SECRET", "integration-only-nonproduction-test-key")
    monkeypatch.setenv("PUBLIC_ORIGIN", "http://testserver")
    get_settings.cache_clear()
    engine = make_engine(get_settings().model_copy(update={"postgres_port": 1}))
    try:
        with TestClient(create_app(engine), client=("127.0.0.1", 50100)) as isolated:
            for path in ("/api/marketplace/vehicles", "/api/auth/csrf"):
                response = isolated.get(path, headers={"origin": "http://testserver"})
                assert response.status_code == 503
                assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"
                assert "data" not in response.json()
                assert "set-cookie" not in response.headers
    finally:
        engine.dispose()
        get_settings.cache_clear()
