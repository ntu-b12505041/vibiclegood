from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine
from test_auth import SOURCE, client_for, register, sign_in
from test_vehicles import vehicle_payload

pytestmark = pytest.mark.integration


def maintenance(day: str, mileage: int) -> dict[str, object]:
    return {"maintenance_date": day, "mileage_km": mileage, "description": "Synthetic service"}


def test_backfill_and_concurrent_incompatible_events(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        email, csrf = register(client)
        headers = {
            **SOURCE,
            "x-csrf-token": sign_in(client, email, csrf).json()["data"]["csrf_token"],
        }
        vehicle = client.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()[
            "data"
        ]
        path = f"/api/vehicles/{vehicle['id']}/maintenance-events"
        for day, mileage in (("2020-03-10", 70000), ("2020-01-10", 50000), ("2020-02-10", 60000)):
            added = client.post(path, headers=headers, json=maintenance(day, mileage))
            assert added.status_code == 201, added.text
        rejected = client.post(path, headers=headers, json=maintenance("2020-02-10", 71000))
        assert rejected.json()["error"]["code"] == "MILEAGE_DATE_CONFLICT"
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(
                client.post, path, headers=headers, json=maintenance("2020-01-20", 59000)
            )
            b = pool.submit(
                client.post, path, headers=headers, json=maintenance("2020-01-21", 55000)
            )
            assert sorted((a.result().status_code, b.result().status_code)) == [201, 422]
        owner_path = f"/api/me/vehicles/{vehicle['id']}"
        timeline = client.get(owner_path + "/maintenance-events")
        assert timeline.status_code == 200, timeline.text
        items = timeline.json()["data"]["items"]
        assert len(items) == 4 and items[0]["current_version"]["maintenance_date"] == "2020-03-10"
        assert client.get(owner_path).json()["data"]["current_mileage_km"] == 80000
        assert client.get(owner_path + "/maintenance-events?page=2").status_code == 422
        changed = client.get(owner_path + "/maintenance-events?page=2&snapshot_row_version=1")
        assert changed.json()["error"]["code"] == "COLLECTION_CHANGED"


def test_correction_is_append_only_releases_high_mileage(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        email, csrf = register(client)
        headers = {
            **SOURCE,
            "x-csrf-token": sign_in(client, email, csrf).json()["data"]["csrf_token"],
        }
        vehicle = client.post(
            "/api/vehicles",
            headers=headers,
            json={**vehicle_payload(), "current_mileage_km": 900000},
        ).json()["data"]
        path = f"/api/vehicles/{vehicle['id']}"
        original = client.post(
            path + "/maintenance-events", headers=headers, json=maintenance("2020-03-10", 900000)
        ).json()["data"]
        decrease = {
            "expected_row_version": original["vehicle_row_version"],
            "current_mileage_km": 80000,
            "mileage_change_reason": "Correct odometer",
            "mileage_decrease_confirmed": True,
        }
        denied = client.patch(path, headers=headers, json=decrease)
        assert denied.json()["error"]["code"] == "MILEAGE_BELOW_EFFECTIVE_HISTORY"
        event_path = path + "/maintenance-events/" + original["event"]["id"]
        correction = {
            **maintenance("2020-03-10", 70000),
            "correction_reason": "Fix original typo",
            "expected_current_version_id": original["created_version_id"],
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            work = [
                pool.submit(
                    client.post, event_path + "/corrections", headers=headers, json=correction
                )
                for _ in range(2)
            ]
            results = [future.result() for future in work]
        assert sorted(result.status_code for result in results) == [201, 409]
        corrected = next(result.json()["data"] for result in results if result.status_code == 201)
        owner_path = f"/api/me/vehicles/{vehicle['id']}"
        assert client.get(owner_path).json()["data"]["current_mileage_km"] == 900000
        versions = client.get(event_path.replace("/api/vehicles", "/api/me/vehicles") + "/versions")
        items = versions.json()["data"]["items"]
        assert [item["mileage_km"] for item in items] == [900000, 70000]
        assert [item["is_effective"] for item in items] == [False, True]
        assert items[1]["previous_version_id"] == items[0]["id"]
        decrease["expected_row_version"] = corrected["vehicle_row_version"]
        saved = client.patch(path, headers=headers, json=decrease)
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["vehicle"]["current_mileage_km"] == 80000


def test_concurrent_current_mileage_and_new_history(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        email, csrf = register(client)
        headers = {
            **SOURCE,
            "x-csrf-token": sign_in(client, email, csrf).json()["data"]["csrf_token"],
        }
        vehicle = client.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()[
            "data"
        ]
        path = f"/api/vehicles/{vehicle['id']}"
        initial = client.post(
            path + "/maintenance-events",
            headers=headers,
            json=maintenance("2020-02-01", 70000),
        )
        assert initial.status_code == 201, initial.text
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit = pool.submit(
                client.patch,
                path,
                headers=headers,
                json={
                    "expected_row_version": "2",
                    "current_mileage_km": 75000,
                    "mileage_decrease_confirmed": True,
                    "mileage_change_reason": "correct C",
                },
            )
            entry = pool.submit(
                client.post,
                path + "/maintenance-events",
                headers=headers,
                json=maintenance("2020-03-01", 78000),
            )
            assert (edit.result().status_code, entry.result().status_code) in {
                (200, 422),
                (409, 201),
            }
        detail = client.get(f"/api/me/vehicles/{vehicle['id']}").json()["data"]
        timeline = client.get(f"/api/me/vehicles/{vehicle['id']}/maintenance-events").json()["data"]
        highest = max(row["current_version"]["mileage_km"] for row in timeline["items"])
        assert detail["current_mileage_km"] >= highest


def test_version_chain_second_correction_and_collection_pagination(auth_engine: Engine) -> None:
    with client_for(auth_engine) as client:
        email, csrf = register(client)
        headers = {
            **SOURCE,
            "x-csrf-token": sign_in(client, email, csrf).json()["data"]["csrf_token"],
        }
        vehicle = client.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()[
            "data"
        ]
        path = f"/api/vehicles/{vehicle['id']}/maintenance-events"
        added = client.post(path, headers=headers, json=maintenance("2020-01-01", 40000))
        assert added.status_code == 201, added.text
        event = added.json()["data"]
        event_path = path + "/" + event["event"]["id"]
        original = event["created_version_id"]
        parent = original
        for index in range(20):
            replacement = client.post(
                event_path + "/corrections",
                headers=headers,
                json={
                    **maintenance("2020-01-01", 40000 + index),
                    "correction_reason": f"Synthetic correction {index}",
                    "expected_current_version_id": parent,
                },
            )
            assert replacement.status_code == 201, replacement.text
            parent = replacement.json()["data"]["created_version_id"]
        stale = client.post(
            event_path + "/corrections",
            headers=headers,
            json={
                **maintenance("2020-01-01", 40000),
                "correction_reason": "Stale parent",
                "expected_current_version_id": original,
            },
        )
        assert stale.status_code == 409 and stale.json()["error"]["outcome"] == "not_applied"
        versions = event_path.replace("/api/vehicles", "/api/me/vehicles") + "/versions"
        first = client.get(versions).json()["data"]
        assert len(first["items"]) == 20 and first["pagination"]["total_items"] == 21
        assert not any(version["is_effective"] for version in first["items"])
        second = client.get(
            versions,
            params={
                "page": 2,
                "snapshot_row_version": first["vehicle_row_version"],
            },
        ).json()["data"]
        assert len(second["items"]) == 1 and second["items"][0]["id"] == parent
        assert second["items"][0]["is_effective"] is True
        assert client.patch(
            event_path + "/versions/" + original, headers=headers, json={}
        ).status_code in (404, 405)


def test_history_owner_and_server_fields_are_enforced(auth_engine: Engine) -> None:
    with client_for(auth_engine) as owner, client_for(auth_engine) as other:
        email, csrf = register(owner)
        login = sign_in(owner, email, csrf).json()["data"]
        headers = {**SOURCE, "x-csrf-token": login["csrf_token"]}
        email, csrf = register(other)
        other_headers = {
            **SOURCE,
            "x-csrf-token": sign_in(other, email, csrf).json()["data"]["csrf_token"],
        }
        one = owner.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()["data"][
            "id"
        ]
        two = owner.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()["data"][
            "id"
        ]
        path = f"/api/vehicles/{one}/maintenance-events"
        original = maintenance("1900-01-01", 30000)
        assert other.post(path, headers=other_headers, json=original).status_code == 404
        for key in ("source", "submitted_by_user_id", "submitted_at", "owner_user_id"):
            assert (
                owner.post(path, headers=headers, json={**original, key: "fake"}).status_code == 422
            )
        saved = owner.post(path, headers=headers, json=original)
        assert saved.status_code == 201
        event = saved.json()["data"]
        assert event["event"]["current_version"]["source"] == "owner_self_reported"
        assert event["event"]["current_version"]["submitted_by_user_id"] == login["user"]["id"]
        same_day = owner.post(path, headers=headers, json=maintenance("1900-01-01", 29000))
        assert same_day.status_code == 201
        invalid = owner.post(path, headers=headers, json=maintenance("2999-01-01", 31000))
        assert invalid.status_code == 422
        assert (
            owner.post(path, headers=headers, json=maintenance("1900-01-02", 90000)).status_code
            == 422
        )
        correction_path = path + "/" + event["event"]["id"] + "/corrections"
        correction = {**original, "expected_current_version_id": event["created_version_id"]}
        assert owner.post(correction_path, headers=headers, json=correction).status_code == 422
        correction["correction_reason"] = "Demo"
        assert (
            other.post(correction_path, headers=other_headers, json=correction).status_code == 404
        )
        cross_vehicle = correction_path.replace(one, two)
        assert owner.post(cross_vehicle, headers=headers, json=correction).status_code == 404


def test_native_maintenance_constraints_and_rollback(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID, uuid4

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from vibicle_api.errors import reject
    from vibicle_api.models import MaintenanceEvent, MaintenanceRecordVersion

    with client_for(auth_engine) as owner:
        email, csrf = register(owner)
        login = sign_in(owner, email, csrf).json()["data"]
        headers = {**SOURCE, "x-csrf-token": login["csrf_token"]}
        car = owner.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()["data"]
        root = f"/api/vehicles/{car['id']}/maintenance-events"
        results = [
            owner.post(root, headers=headers, json=maintenance("2020-01-01", km)).json()["data"]
            for km in (30000, 31000)
        ]
        a = results[0]
        event_a = UUID(a["event"]["id"])
        version_a, version_b = (UUID(item["created_version_id"]) for item in results)
        with pytest.raises(IntegrityError), Session(auth_engine) as db:
            event = db.get(MaintenanceEvent, event_a)
            assert event is not None
            event.current_version_id = version_b
            db.flush()  # F-02 rejects at commit rather than at the statement.
            db.commit()
        for previous_mode in ("cross", "self"):
            with pytest.raises(IntegrityError), Session(auth_engine) as db:
                original = db.get(MaintenanceRecordVersion, version_a)
                assert original is not None
                next_id = uuid4()
                db.add(
                    MaintenanceRecordVersion(
                        id=next_id,
                        event_id=event_a,
                        previous_version_id=version_b if previous_mode == "cross" else next_id,
                        version_no=2,
                        maintenance_date=original.maintenance_date,
                        mileage_km=31000,
                        description="synthetic",
                        correction_reason="synthetic",
                        submitted_by_user_id=original.submitted_by_user_id,
                    )
                )
                db.commit()
        payload = {
            **maintenance("2020-01-01", 30000),
            "expected_current_version_id": a["created_version_id"],
            "correction_reason": "Fixture rollback",
        }

        def stop_before_commit(db):
            reject(503, "STORE_UNAVAILABLE", "Test transaction deliberately rolled back.")

        with monkeypatch.context() as patched:
            patched.setattr("vibicle_api.services.history.commit", stop_before_commit)
            failed = owner.post(root + f"/{event_a}/corrections", headers=headers, json=payload)
            assert failed.status_code == 503 and failed.json()["error"]["outcome"] == "not_applied"
        chain_path = root.replace("/api/vehicles", "/api/me/vehicles") + f"/{event_a}/versions"
        chain = owner.get(chain_path).json()["data"]["items"]
        assert [item["id"] for item in chain] == [str(version_a)]
        assert chain[0]["is_effective"] is True
        assert owner.delete(chain_path, headers=headers).status_code == 405
        assert owner.patch(chain_path, headers=headers, json={}).status_code == 405
        assert owner.get(chain_path).json()["data"]["items"] == chain
