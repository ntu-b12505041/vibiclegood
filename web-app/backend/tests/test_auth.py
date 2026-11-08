from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from vibicle_api.main import create_app
from vibicle_api.models import AppUser, AuthSession
from vibicle_api.services.identity import SESSION_COOKIE, decode_token

ORIGIN = "https://vibicle.localhost:8443"
SOURCE = {"origin": ORIGIN, "sec-fetch-site": "same-origin"}
PASSWORD = "  環境測試😀 safe pass  "
pytestmark = pytest.mark.integration


def client_for(engine: Engine) -> TestClient:
    return TestClient(create_app(engine), base_url=ORIGIN, client=("127.0.0.1", 50000))


def bootstrap(client: TestClient) -> str:
    res = client.get("/api/auth/csrf", headers=SOURCE)
    assert res.status_code == 200, res.text
    return res.json()["data"]["csrf_token"]


def register(client: TestClient, *, prefix: str = "") -> tuple[str, str]:
    csrf = bootstrap(client)
    email = prefix + uuid4().hex + "@example.test"
    res = client.post(
        "/api/auth/register",
        headers={**SOURCE, "x-csrf-token": csrf},
        json={"email": email, "password": PASSWORD, "password_confirmation": PASSWORD},
    )
    assert res.status_code == 201, res.text
    assert "set-cookie" not in res.headers
    assert not client.get("/api/auth/me").json()["data"]["authenticated"]
    return email, csrf


def sign_in(client: TestClient, email: str, csrf: str):
    return client.post(
        "/api/auth/login",
        headers={**SOURCE, "x-csrf-token": csrf},
        json={"email": email, "password": PASSWORD},
    )


def test_registration_rotation_replay_logout_other_device(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client, client_for(auth_engine) as independent:
        email, csrf = register(client, prefix="É")
        preauth = client.cookies[SESSION_COOKIE]
        res = sign_in(client, "　" + email.upper() + "　", csrf)
        assert res.status_code == 200, res.text
        flags = res.headers["set-cookie"].lower()
        assert all(
            flag in flags
            for flag in ("secure", "httponly", "samesite=lax", "path=/", "max-age=28800")
        )
        assert "domain=" not in flags
        assert client.cookies[SESSION_COOKIE] != preauth
        new_csrf = res.json()["data"]["csrf_token"]
        assert new_csrf != csrf
        assert preauth not in res.text and client.cookies[SESSION_COOKIE] not in res.text
        sid = client.cookies[SESSION_COOKIE]
        with Session(auth_engine) as db:
            raw = decode_token(sid)
            assert raw is not None
            row = db.get(AuthSession, sha256(raw).digest())
            assert row is not None and row.absolute_expires_at - row.created_at == timedelta(
                hours=8
            )
            assert row.user_id is not None
            user = db.get(AppUser, row.user_id)
            assert user is not None and user.password_hash.startswith("$argon2id$")
        assert sign_in(independent, email, bootstrap(independent)).status_code == 200
        replay = {"cookie": SESSION_COOKIE + "=" + preauth, **SOURCE, "x-csrf-token": csrf}
        assert (
            client.post(
                "/api/auth/login", headers=replay, json={"email": email, "password": PASSWORD}
            ).status_code
            == 403
        )
        assert client.get("/api/auth/me").json()["data"]["authenticated"]
        assert "set-cookie" not in client.get("/api/auth/me").headers
        out = client.post("/api/auth/logout", headers={**SOURCE, "x-csrf-token": new_csrf})
        assert (
            out.status_code == 204 and not out.content and "Max-Age=0" in out.headers["set-cookie"]
        )
        replay = {"cookie": SESSION_COOKIE + "=" + sid}
        assert not client.get("/api/auth/me", headers=replay).json()["data"]["authenticated"]
        assert (
            client.post(
                "/api/auth/logout", headers={**SOURCE, **replay, "x-csrf-token": new_csrf}
            ).status_code
            == 204
        )
        assert independent.get("/api/auth/me").json()["data"]["authenticated"]


def test_source_csrf_gate_and_expiry(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        assert client.get("/api/auth/csrf").status_code == 403
        assert (
            client.get(
                "/api/auth/csrf", headers={**SOURCE, "origin": "https://vibicle.localhost"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/auth/csrf", headers={**SOURCE, "sec-fetch-site": "same-site"}
            ).status_code
            == 403
        )
        email, csrf = register(client)
        assert (
            client.post("/api/auth/login", headers=SOURCE, content=b"not-json").json()["error"][
                "code"
            ]
            == "CSRF_INVALID"
        )
        assert sign_in(client, email, "A" * 43).json()["error"]["code"] == "CSRF_INVALID"
        success = sign_in(client, email, csrf)
        assert success.status_code == 200
        raw = decode_token(client.cookies[SESSION_COOKIE])
        assert raw is not None
        token = sha256(raw).digest()
        with Session(auth_engine) as db:
            now = db.scalar(select(func.clock_timestamp()))
            row = db.get(AuthSession, token)
            assert now is not None and row is not None
            row.created_at = now - timedelta(hours=1)
            row.absolute_expires_at = row.created_at + timedelta(hours=8)
            row.last_activity_at = now - timedelta(minutes=30)
            db.commit()
        assert not client.get("/api/auth/me").json()["data"]["authenticated"]
        assert (
            client.post(
                "/api/auth/logout",
                headers={**SOURCE, "x-csrf-token": success.json()["data"]["csrf_token"]},
            ).status_code
            == 204
        )


def test_rate_limit_counts_invalid_context_independently(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        for _ in range(20):
            res = client.post("/api/auth/login", headers=SOURCE)
            assert res.status_code == 403
        res = client.post("/api/auth/login", headers=SOURCE)
        assert res.status_code == 429 and 1 <= int(res.headers["retry-after"]) <= 300
        assert "set-cookie" not in res.headers


def test_email_unique_and_wrong_credentials(
    auth_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import BoundedSemaphore

    # Two KDF slots simulate two independent workers while both use real PG connections.
    monkeypatch.setattr("vibicle_api.services.auth.KDF_SLOT", BoundedSemaphore(2))
    with client_for(auth_engine) as a, client_for(auth_engine) as b:
        email = "Cafe\u0301-" + uuid4().hex + "@example.test"
        ca, cb = bootstrap(a), bootstrap(b)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [
                pool.submit(
                    client.post,
                    "/api/auth/register",
                    headers={**SOURCE, "x-csrf-token": csrf},
                    json={"email": addr, "password": PASSWORD, "password_confirmation": PASSWORD},
                )
                for client, csrf, addr in ((a, ca, email), (b, cb, "　" + email.upper() + " "))
            ]
            assert sorted(res.result().status_code for res in responses) == [201, 409]
        for candidate in (email, f"missing-{uuid4().hex}@example.test"):
            res = a.post(
                "/api/auth/login",
                headers={**SOURCE, "x-csrf-token": ca},
                json={"email": candidate, "password": "valid-length wrong pass"},
            )
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"
            assert "set-cookie" not in res.headers
        assert a.get("/api/me/vehicles").status_code == 401
        assert sign_in(a, email, ca).status_code == 200


def test_same_context_concurrent_rotation(
    auth_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, BoundedSemaphore

    from vibicle_api.services.auth import AuthService

    with client_for(auth_engine) as client:
        email, csrf = register(client)
        token = client.cookies[SESSION_COOKIE]
        wait = Barrier(2, timeout=10)
        check = AuthService.check_context

        def simultaneous(service, token, csrf, **options):
            checked = check(service, token, csrf, **options)
            wait.wait()
            return checked

        monkeypatch.setattr("vibicle_api.services.auth.KDF_SLOT", BoundedSemaphore(2))
        monkeypatch.setattr(AuthService, "check_context", simultaneous)
        with client_for(auth_engine) as a, client_for(auth_engine) as b:
            headers = {**SOURCE, "x-csrf-token": csrf, "cookie": f"{SESSION_COOKIE}={token}"}
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [
                    pool.submit(
                        c.post,
                        "/api/auth/login",
                        headers=headers,
                        json={"email": email, "password": PASSWORD},
                    )
                    for c in (a, b)
                ]
                responses = sorted((job.result() for job in jobs), key=lambda r: r.status_code)
            assert [res.status_code for res in responses] == [200, 409]
            assert "set-cookie" not in responses[1].headers


def test_logout_replay_and_touch_waiter(auth_engine: Engine) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from vibicle_api.repositories.auth import clock
    from vibicle_api.services.auth import AuthService

    with client_for(auth_engine) as client:
        email, csrf = register(client)
        csrf = sign_in(client, email, csrf).json()["data"]["csrf_token"]
        sid = client.cookies[SESSION_COOKIE]
        raw = decode_token(sid)
        assert raw is not None
        hashed = sha256(raw).digest()
        service = AuthService(auth_engine)
        with ThreadPoolExecutor(max_workers=1) as pool, Session(auth_engine) as db:
            row = db.get(AuthSession, hashed, with_for_update=True)
            assert row is not None
            previous_activity = row.last_activity_at
            waiting_touch = pool.submit(service.touch, hashed)
            row.revoked_at = clock(db)
            db.commit()
            assert waiting_touch.result().reason == "SESSION_REVOKED"
        with Session(auth_engine) as db:
            row = db.get(AuthSession, hashed)
            assert row is not None and row.revoked_at and row.last_activity_at == previous_activity
        assert client.get("/api/me/vehicles").status_code == 401
        res = client.post("/api/vehicles", headers={**SOURCE, "x-csrf-token": csrf}, json={})
        assert res.status_code == 401 and "set-cookie" not in res.headers


@pytest.mark.parametrize("scope", ["register", "csrf_context", "login"])
def test_rate_limit_across_workers(auth_engine: Engine, scope: str) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from vibicle_api.errors import ContractError
    from vibicle_api.services.auth import RATE_POLICY, AuthService

    a, b = AuthService(auth_engine), AuthService(auth_engine)
    secret = uuid4().bytes + uuid4().bytes
    limit, _ = RATE_POLICY[scope]

    def hit(index: int) -> int:
        try:
            (a if index % 2 else b).rate_gate(scope, "127.0.0.1", secret)
        except ContractError as error:
            assert error.status == 429 and error.retry_after and error.retry_after > 0
            return 429
        return 200

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(hit, range(limit + 3)))
    assert results.count(200) == limit and results.count(429) == 3


def test_registration_validation_no_secret_echo(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        csrf = bootstrap(client)
        payload = {"email": "invalid", "password": PASSWORD, "password_confirmation": PASSWORD}
        assert client.post("/api/auth/register", headers=SOURCE, json=payload).status_code == 403
        invalid = client.post(
            "/api/auth/register",
            headers={**SOURCE, "x-csrf-token": csrf},
            json=payload,
        )
        assert invalid.status_code == 422 and PASSWORD not in invalid.text
        repeated = client.post(
            "/api/auth/register",
            headers={**SOURCE, "x-csrf-token": csrf, "content-type": "application/json"},
            content=b'{"email":"first@example.test","email":"second@example.test"}',
        )
        assert repeated.status_code == 400 and repeated.json()["error"]["code"] == "DUPLICATE_FIELD"
        assert "set-cookie" not in invalid.headers and "input" not in invalid.text
        assert client.get("/api/me/vehicles").status_code == 401
        assert client.get("/api/auth/logout").status_code == 405


@pytest.mark.parametrize(
    ("created_ago", "last_ago", "kind", "valid"),
    [
        (3600, 1799, "authenticated", True),
        (3600, 1800, "authenticated", False),
        (28799, 10, "authenticated", True),
        (28800, 10, "authenticated", False),
        (899, 899, "preauth", True),
        (900, 900, "preauth", False),
    ],
)
def test_exact_expiration_predicate(
    created_ago: int,
    last_ago: int,
    kind: str,
    valid: bool,
) -> None:
    from datetime import UTC, datetime

    from vibicle_api.services.identity import active

    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    created = now - timedelta(seconds=created_ago)
    row = AuthSession(
        kind=kind,
        created_at=created,
        last_activity_at=now - timedelta(seconds=last_ago),
        absolute_expires_at=created + timedelta(minutes=15 if kind == "preauth" else 480),
    )
    assert active(row, now) is valid


def test_absolute_expiry_and_activity_policy(auth_engine: Engine) -> None:
    from vibicle_api.repositories.auth import clock

    with client_for(auth_engine) as client:
        email, preauth = register(client)
        bootstrap_again = client.get("/api/auth/csrf", headers=SOURCE)
        assert bootstrap_again.json()["data"]["csrf_token"] == preauth
        assert "set-cookie" not in bootstrap_again.headers
        response = sign_in(client, email, preauth)
        assert response.status_code == 200
        csrf = response.json()["data"]["csrf_token"]
        token = decode_token(client.cookies[SESSION_COOKIE])
        assert token is not None
        token_hash = sha256(token).digest()
        with Session(auth_engine) as db:
            row = db.get(AuthSession, token_hash)
            assert row is not None
            now = clock(db)
            row.created_at = now - timedelta(hours=7, minutes=58)
            row.absolute_expires_at = row.created_at + timedelta(hours=8)
            row.last_activity_at = now - timedelta(minutes=2)
            previous, absolute = row.last_activity_at, row.absolute_expires_at
            db.commit()
        for path, headers in (
            ("/api/auth/me", {}),
            ("/api/auth/csrf", SOURCE),
            ("/api/marketplace/vehicles", {}),
            ("/api/vehicles/" + str(uuid4()) + "/images/" + str(uuid4()), {}),
        ):
            result = client.get(path, headers=headers)
            assert result.status_code in (200, 404)
            assert "set-cookie" not in result.headers
        rejected = client.post("/api/vehicles", headers=SOURCE, json={})
        assert rejected.status_code == 403
        with Session(auth_engine) as db:
            row = db.get(AuthSession, token_hash)
            assert row is not None and row.last_activity_at == previous
        touched = client.get("/api/me/vehicles")
        assert touched.json()["meta"]["session"]["activity"] == "touched"
        assert "set-cookie" not in touched.headers
        with Session(auth_engine) as db:
            row = db.get(AuthSession, token_hash)
            assert row is not None and row.absolute_expires_at == absolute
            assert row.last_activity_at > previous
            now = clock(db)
            row.created_at = now - timedelta(hours=8, seconds=1)
            row.absolute_expires_at = row.created_at + timedelta(hours=8)
            row.last_activity_at = row.absolute_expires_at - timedelta(seconds=1)
            db.commit()
        assert client.get("/api/auth/me").json()["data"]["authenticated"] is False
        assert client.get("/api/me/vehicles").status_code == 401
        forged = {"cookie": SESSION_COOKIE + "=" + "A" * 43}
        assert client.get("/api/me/vehicles", headers=forged).status_code == 401
        assert (
            client.post(
                "/api/vehicles", headers={**SOURCE, "x-csrf-token": csrf}, json={}
            ).status_code
            == 401
        )
