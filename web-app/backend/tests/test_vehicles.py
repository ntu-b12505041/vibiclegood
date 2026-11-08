from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from test_auth import SOURCE, client_for, register, sign_in

from vibicle_api.models import VehicleMileageChange
from vibicle_api.schemas import SessionMeta
from vibicle_api.services.auth import AuthService

pytestmark = pytest.mark.integration


def vehicle_payload() -> dict[str, object]:
    return {
        "vin": "TEST" + uuid4().hex[:13].upper(),
        "brand": "Demo",
        "model": "Trail",
        "model_year": 2020,
        "current_mileage_km": 80000,
        "price_twd": 330000,
    }


def test_vehicle_owner_and_initial_ledger(auth_engine: Engine) -> None:
    with client_for(auth_engine) as owner, client_for(auth_engine) as other:
        assert owner.get("/api/me/vehicles").status_code == 401
        user_email, token = register(owner)
        credentials = sign_in(owner, user_email, token)
        token = credentials.json()["data"]["csrf_token"]
        body = vehicle_payload()
        denied = owner.post("/api/vehicles", json=body, headers=SOURCE)
        assert denied.status_code == 403
        res = owner.post("/api/vehicles", json=body, headers={**SOURCE, "x-csrf-token": token})
        assert res.status_code == 201, res.text
        data = res.json()["data"]
        assert data["row_version"] == "1" and data["vin"] == body["vin"] and not data["is_listed"]
        assert res.json()["meta"]["session"]["activity"] == "touched"
        assert "set-cookie" not in res.headers
        owner_path = res.headers["Location"]
        with Session(auth_engine) as db:
            changes = list(
                db.scalars(
                    select(VehicleMileageChange).where(
                        VehicleMileageChange.vehicle_id == UUID(data["id"])
                    )
                )
            )
            assert len(changes) == 1
            assert changes[0].previous_mileage_km is None
            assert changes[0].new_mileage_km == 80000 and changes[0].vehicle_revision == 1
        email, csrf = register(other)
        other_login = sign_in(other, email, csrf)
        assert other_login.status_code == 200
        assert other.get(owner_path).status_code == 404
        assert other.get("/api/me/vehicles").json()["data"]["items"] == []
        other_created = other.post(
            "/api/vehicles",
            json=vehicle_payload(),
            headers={**SOURCE, "x-csrf-token": other_login.json()["data"]["csrf_token"]},
        )
        assert other_created.status_code == 201
        other_id = other_created.json()["data"]["id"]
        assert owner.get(owner_path).json()["data"]["vin"] == body["vin"]
        garage = owner.get("/api/me/vehicles?page=1").json()["data"]
        assert garage["items"][0]["id"] == data["id"] and garage["pagination"]["page_size"] == 20
        assert other_id not in {item["id"] for item in garage["items"]}
        assert owner.get("/api/me/vehicles?owner_user_id=" + str(uuid4())).status_code == 422
        assert owner.get("/api/me/vehicles?page=999").json()["data"]["items"] == []


def test_parallel_duplicate_vin_and_touch_failure(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with client_for(auth_engine) as first, client_for(auth_engine) as second:
        headers = []
        for client in (first, second):
            email, token = register(client)
            csrf = sign_in(client, email, token).json()["data"]["csrf_token"]
            headers.append({**SOURCE, "x-csrf-token": csrf})
        body = vehicle_payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(first.post, "/api/vehicles", headers=headers[0], json=body)
            alternate = {**body, "vin": "  " + str(body["vin"]).lower() + "  "}
            b = pool.submit(second.post, "/api/vehicles", headers=headers[1], json=alternate)
            assert sorted([a.result().status_code, b.result().status_code]) == [201, 409]

        def unavailable(self: AuthService, token: bytes) -> SessionMeta:
            return SessionMeta(
                activity="unknown", requires_revalidation=True, reason="SESSION_STORE_UNAVAILABLE"
            )

        monkeypatch.setattr(AuthService, "touch", unavailable)
        saved = first.post("/api/vehicles", headers=headers[0], json=vehicle_payload())
        assert saved.status_code == 201
        assert saved.json()["meta"]["business_outcome"] == "committed"
        assert saved.json()["meta"]["session"]["activity"] == "unknown"
        assert first.get(saved.headers["Location"]).status_code == 200


def test_revision_lock_and_mileage_ledger(auth_engine: Engine) -> None:
    with client_for(auth_engine) as a, client_for(auth_engine) as b:
        email, csrf = register(a)
        h_a = {**SOURCE, "x-csrf-token": sign_in(a, email, csrf).json()["data"]["csrf_token"]}
        other, csrf = register(b)
        h_b = {**SOURCE, "x-csrf-token": sign_in(b, other, csrf).json()["data"]["csrf_token"]}
        created = a.post("/api/vehicles", headers=h_a, json=vehicle_payload()).json()["data"]
        path = "/api/vehicles/" + created["id"]
        body = {"expected_row_version": "1", "current_mileage_km": 75000}
        assert b.patch(path, headers=h_b, json=body).status_code == 404
        for field in ("owner_user_id", "source", "submitted_at"):
            refused = a.patch(path, headers=h_a, json={**body, field: "client-selected"})
            assert refused.status_code == 422
        assert a.patch(path, headers=h_a, json=body).json()["error"]["code"] == (
            "MILEAGE_DECREASE_REASON_REQUIRED"
        )
        body.update(mileage_change_reason="Correct transcription", mileage_decrease_confirmed=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(a.patch, path, headers=h_a, json=body) for _ in range(2)]
            assert sorted(result.result().status_code for result in results) == [200, 409]
        noop = a.patch(
            path, headers=h_a, json={"expected_row_version": "2", "current_mileage_km": 75000}
        )
        assert noop.json()["data"]["changed"] is False
        ledger = a.get("/api/me/vehicles/" + created["id"] + "/mileage-changes").json()
        items = ledger["data"]["items"]
        assert [item["new_mileage_km"] for item in items] == [75000, 80000]
        assert items[0]["previous_mileage_km"] == 80000
        assert items[0]["reason"] == "Correct transcription"
        increase = a.patch(
            path,
            headers=h_a,
            json={"expected_row_version": "2", "current_mileage_km": 79000},
        )
        assert increase.status_code == 200
        ledger_path = "/api/me/vehicles/" + created["id"] + "/mileage-changes"
        items = a.get(ledger_path).json()["data"]["items"]
        assert [item["new_mileage_km"] for item in items] == [79000, 75000, 80000]
        assert b.get(ledger_path).status_code == 404


def test_hidden_vehicle_rejects_owner_override_and_rolls_back_initial_ledger(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibicle_api.errors import reject
    from vibicle_api.models import Vehicle

    with client_for(auth_engine) as client, client_for(auth_engine) as visitor:
        email, csrf = register(client)
        headers = {
            **SOURCE,
            "x-csrf-token": sign_in(client, email, csrf).json()["data"]["csrf_token"],
        }
        body = vehicle_payload()
        assert (
            client.post(
                "/api/vehicles", headers=headers, json={**body, "owner_user_id": str(uuid4())}
            ).status_code
            == 422
        )

        def fail_commit(db):
            db.flush()
            reject(503, "STORE_UNAVAILABLE", "Fixture transaction rolled back.")

        with monkeypatch.context() as patched:
            patched.setattr("vibicle_api.services.vehicles.commit", fail_commit)
            failed = client.post("/api/vehicles", headers=headers, json=body)
            assert failed.json()["error"]["outcome"] == "not_applied"
        with Session(auth_engine) as db:
            assert db.scalar(select(Vehicle).where(Vehicle.vin == body["vin"])) is None
        saved = client.post("/api/vehicles", headers=headers, json=body)
        assert saved.status_code == 201
        row = saved.json()["data"]
        assert row["owner_user_id"] == client.get("/api/auth/me").json()["data"]["user"]["id"]
        assert visitor.get("/api/vehicles/" + row["id"]).status_code == 404
        public = visitor.get("/api/marketplace/vehicles", params={"q": body["vin"]})
        assert public.status_code == 200 and not public.json()["data"]["items"]
