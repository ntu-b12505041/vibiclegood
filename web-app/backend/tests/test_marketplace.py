from pathlib import Path

import pytest
from sqlalchemy import Engine
from test_auth import SOURCE, client_for, register, sign_in
from test_history import maintenance
from test_images import png
from test_vehicles import vehicle_payload

from vibicle_api.config import get_settings

pytestmark = pytest.mark.integration


def test_listing_projection_unlisting_and_old_photo(
    auth_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_IMAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with client_for(auth_engine) as owner, client_for(auth_engine) as visitor:
        email, csrf = register(owner)
        csrf = sign_in(owner, email, csrf).json()["data"]["csrf_token"]
        headers = {**SOURCE, "x-csrf-token": csrf}
        vehicle = owner.post(
            "/api/vehicles",
            json={**vehicle_payload(), "brand": "Rock%_Trail"},
            headers=headers,
        ).json()["data"]
        path = "/api/vehicles/" + vehicle["id"]
        invalid = owner.put(
            path + "/listing",
            json={"is_listed": True, "expected_row_version": "1"},
            headers=headers,
        )
        assert invalid.json()["error"]["code"] == "LISTING_NOT_READY"
        image = owner.post(
            path + "/image",
            files={"file": ("synthetic.png", png(), "image/png")},
            data={"expected_row_version": "1"},
            headers=headers,
        )
        assert image.status_code == 200, image.text
        url = image.headers["location"]
        added = owner.post(
            path + "/maintenance-events", json=maintenance("2021-05-10", 70000), headers=headers
        )
        assert added.status_code == 201, added.text
        event = added.json()["data"]["event"]
        listed = owner.put(
            path + "/listing",
            json={"is_listed": True, "expected_row_version": "3"},
            headers=headers,
        )
        assert listed.status_code == 200, listed.text
        listed_data = listed.json()["data"]["vehicle"]
        assert listed_data["row_version"] == "4"
        duplicate = owner.put(
            path + "/listing",
            json={"is_listed": True, "expected_row_version": "4"},
            headers=headers,
        )
        assert duplicate.json()["data"]["changed"] is False
        assert (
            duplicate.json()["data"]["vehicle"]["last_listed_at"] == listed_data["last_listed_at"]
        )
        page = visitor.get("/api/marketplace/vehicles", params={"q": "rOcK%_tRaIl"})
        assert page.status_code == 200, page.text
        found = page.json()["data"]
        assert found["pagination"]["page_size"] == 12
        assert vehicle["id"] in [row["id"] for row in found["items"]]
        no_match = visitor.get("/api/marketplace/vehicles", params={"q": "RockXATrail"})
        assert vehicle["id"] not in [row["id"] for row in no_match.json()["data"]["items"]]
        detail = owner.get(path)
        assert detail.status_code == 200, detail.text
        exposed = detail.json()["data"]
        assert exposed["vin_suffix"] == vehicle["vin"][-6:]
        assert "vin" not in exposed and "owner_user_id" not in exposed and email not in detail.text
        assert detail.json()["meta"]["session"]["activity"] == "not_applicable"
        denied_patch = owner.patch(
            path,
            json={"price_twd": None, "brand": "Do not persist", "expected_row_version": "4"},
            headers=headers,
        )
        assert denied_patch.status_code == 422
        assert owner.get(path).json()["data"] == exposed
        assert visitor.get(url).status_code == 200
        timeline = visitor.get(path + "/maintenance-events").json()["data"]["items"]
        assert "submitted_by_user_id" not in timeline[0]["current_version"]
        assert timeline[0]["current_version"]["source"] == "owner_self_reported"
        hidden = owner.put(
            path + "/listing",
            json={"is_listed": False, "expected_row_version": "4"},
            headers=headers,
        )
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["data"]["vehicle"]["last_listed_at"] == listed_data["last_listed_at"]
        assert visitor.get(path).status_code == 404
        assert visitor.get(path + "/maintenance-events").status_code == 404
        assert visitor.get(path + f"/maintenance-events/{event['id']}/versions").status_code == 404
        assert visitor.get(url, headers={"If-None-Match": '"old"'}).status_code == 404
        assert owner.get(path).status_code == 404
        assert owner.get(url).status_code == 200


def test_marketplace_fixed_pagination_and_sort(auth_engine: Engine) -> None:
    from datetime import timedelta
    from uuid import UUID, uuid4

    from sqlalchemy.orm import Session

    from vibicle_api.models import Vehicle, VehicleImage
    from vibicle_api.repositories.auth import clock
    from vibicle_api.services.vehicles import VehicleService
    from vibicle_api.vehicle_schemas import VehicleCreate

    with client_for(auth_engine) as owner, client_for(auth_engine) as visitor:
        email, csrf = register(owner)
        user_id = UUID(sign_in(owner, email, csrf).json()["data"]["user"]["id"])
        group = "SYNTHETIC-" + uuid4().hex[:8]
        service = VehicleService(auth_engine)
        ids = [
            service.create(
                user_id,
                VehicleCreate.model_validate(
                    {
                        **vehicle_payload(),
                        "brand": group,
                        "model": f"Trail {index}",
                    }
                ),
            ).id
            for index in range(14)
        ]
        with Session(auth_engine) as db:
            moment = clock(db)
            for index, vehicle_id in enumerate(ids[:-1]):
                row = db.get(Vehicle, vehicle_id)
                image = VehicleImage(
                    id=uuid4(),
                    vehicle_id=vehicle_id,
                    status="ready",
                    expected_vehicle_version=1,
                    media_type="image/png",
                    byte_size=len(png()),
                    width_px=24,
                    height_px=16,
                    processed_at=moment,
                    created_at=moment,
                    updated_at=moment,
                )
                db.add(image)
                db.flush()
                assert row is not None
                row.current_image_id = image.id
                row.last_listed_at = moment - timedelta(seconds=13 - index)
                row.is_listed = True
            db.commit()
        path = "/api/marketplace/vehicles"
        first = visitor.get(path, params={"q": " " + group.lower() + " "}).json()["data"]
        assert [item["id"] for item in first["items"]] == [str(key) for key in ids[1:-1][::-1]]
        assert first["pagination"]["total_items"] == 13 and first["pagination"]["has_next"]
        next_page = visitor.get(path, params={"q": group, "page": 2}).json()["data"]
        assert [item["id"] for item in next_page["items"]] == [str(ids[0])]
        assert visitor.get(path, params={"q": group, "page": 3}).json()["data"]["items"] == []
        assert visitor.get(path, params={"q": "x" * 50}).status_code == 200
        assert visitor.get(path, params={"q": "x" * 51}).status_code == 422


def test_listing_guards_empty_history_and_unlisting_noop(
    auth_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_IMAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with client_for(auth_engine) as owner, client_for(auth_engine) as other:
        email, csrf = register(owner)
        session = sign_in(owner, email, csrf).json()["data"]
        h_owner = {**SOURCE, "x-csrf-token": session["csrf_token"]}
        email, csrf = register(other)
        h_other = {
            **SOURCE,
            "x-csrf-token": sign_in(other, email, csrf).json()["data"]["csrf_token"],
        }
        vehicle = owner.post(
            "/api/vehicles",
            json={**vehicle_payload(), "price_twd": None},
            headers=h_owner,
        ).json()["data"]
        path = "/api/vehicles/" + vehicle["id"]
        h_list = {"is_listed": True, "expected_row_version": "1"}
        assert other.put(path + "/listing", json=h_list, headers=h_other).status_code == 404
        assert other.post(path + "/image", content=b"bad", headers=h_other).status_code == 404
        image = owner.post(
            path + "/image",
            files={"file": ("synthetic.png", png(), "image/png")},
            data={"expected_row_version": "1"},
            headers=h_owner,
        )
        assert image.status_code == 200, image.text
        h_list["expected_row_version"] = "2"
        missing_price = owner.put(path + "/listing", json=h_list, headers=h_owner)
        assert missing_price.status_code == 422
        assert other.get(path).status_code == 404
        valid = owner.patch(
            path,
            headers=h_owner,
            json={
                "price_twd": 220000,
                "expected_row_version": "2",
            },
        )
        assert valid.status_code == 200
        h_list["expected_row_version"] = "3"
        listed = owner.put(path + "/listing", json=h_list, headers=h_owner)
        assert listed.status_code == 200 and listed.json()["data"]["vehicle"]["is_listed"]
        assert other.get(path + "/maintenance-events").json()["data"]["items"] == []
        for bad in ({"price_twd": None, "brand": "Should not persist"}, {"vin": vehicle["vin"]}):
            failed = owner.patch(path, headers=h_owner, json={**bad, "expected_row_version": "4"})
            assert failed.status_code == 422
        assert other.get(path).json()["data"]["brand"] == vehicle["brand"]
        down = owner.put(
            path + "/listing",
            headers=h_owner,
            json={
                "is_listed": False,
                "expected_row_version": "4",
            },
        )
        assert down.status_code == 200
        again = owner.put(
            path + "/listing",
            headers=h_owner,
            json={
                "is_listed": False,
                "expected_row_version": "5",
            },
        )
        assert again.status_code == 200 and again.json()["data"]["changed"] is False
        assert again.json()["data"]["vehicle"]["price_twd"] == 220000
        assert (
            other.get(image.headers["location"], headers={"Range": "bytes=0-5"}).status_code == 404
        )
        public = other.get("/api/marketplace/vehicles", params={"q": vehicle["brand"]}).json()
        assert vehicle["id"] not in [item["id"] for item in public["data"]["items"]]
        relisted = owner.put(
            path + "/listing",
            headers=h_owner,
            json={"is_listed": True, "expected_row_version": "5"},
        )
        assert relisted.status_code == 200
        relisted_at = relisted.json()["data"]["vehicle"]["last_listed_at"]
        assert relisted_at > listed.json()["data"]["vehicle"]["last_listed_at"]


def test_listing_and_image_replacement_share_vehicle_lock(
    auth_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("PRIVATE_IMAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with client_for(auth_engine) as owner:
        email, csrf = register(owner)
        login = sign_in(owner, email, csrf).json()["data"]
        headers = {**SOURCE, "x-csrf-token": login["csrf_token"]}
        vehicle = owner.post("/api/vehicles", headers=headers, json=vehicle_payload()).json()[
            "data"
        ]
        path = "/api/vehicles/" + vehicle["id"]
        files = {"file": ("synthetic.png", png(), "image/png")}
        first = owner.post(
            path + "/image",
            headers=headers,
            files=files,
            data={"expected_row_version": "1"},
        )
        assert first.status_code == 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            image = pool.submit(
                owner.post,
                path + "/image",
                headers=headers,
                files=files,
                data={"expected_row_version": "2"},
            )
            listing = pool.submit(
                owner.put,
                path + "/listing",
                headers=headers,
                json={"expected_row_version": "2", "is_listed": True},
            )
            status = (image.result().status_code, listing.result().status_code)
        assert status in ((200, 409), (409, 200))
        saved = owner.get("/api/me/vehicles/" + vehicle["id"]).json()["data"]
        assert saved["row_version"] == "3"
        assert saved["is_listed"] == (status[1] == 200)
