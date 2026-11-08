from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import Engine
from test_auth import SOURCE, client_for, register, sign_in
from test_vehicles import vehicle_payload

from vibicle_api.config import get_settings

pytestmark = pytest.mark.integration


def png() -> bytes:
    out = BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "private synthetic metadata")
    Image.new("RGB", (24, 16), (22, 72, 59)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


def test_image_is_private_processed_and_replaced(
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
        created = owner.post("/api/vehicles", json=vehicle_payload(), headers=headers).json()[
            "data"
        ]
        path = "/api/vehicles/" + created["id"] + "/image"
        files = {"file": ("unsafe-name.png", png(), "image/png")}
        uploaded = owner.post(
            path, files=files, data={"expected_row_version": "1"}, headers=headers
        )
        assert uploaded.status_code == 200, uploaded.text
        first_url = uploaded.headers["Location"]
        assert first_url == uploaded.json()["data"]["image"]["url"]
        assert visitor.get(first_url, headers={"If-None-Match": "test"}).status_code == 404
        fetched = owner.get(first_url, headers={"Range": "bytes=0-1"})
        assert fetched.status_code == 200 and fetched.headers["cache-control"] == "no-store"
        assert fetched.headers["x-content-type-options"] == "nosniff"
        assert fetched.headers["content-type"] == "image/png"
        assert "etag" not in fetched.headers and "accept-ranges" not in fetched.headers
        assert owner.get(first_url, headers={"If-None-Match": "test"}).status_code == 400
        with Image.open(BytesIO(fetched.content)) as decoded:
            assert decoded.size == (24, 16) and "Comment" not in decoded.info
        invalid = {"file": ("fake.jpg", png(), "image/jpeg")}
        failed = owner.post(
            path, files=invalid, data={"expected_row_version": "2"}, headers=headers
        )
        assert failed.status_code == 415 and owner.get(first_url).status_code == 200
        corrupt = owner.post(
            path,
            files={"file": ("corrupt.png", b"\x89PNG\r\n\x1a\n", "image/png")},
            data={"expected_row_version": "2"},
            headers=headers,
        )
        assert corrupt.status_code == 422
        assert owner.get(first_url).status_code == 200
        replaced = owner.post(
            path, files=files, data={"expected_row_version": "2"}, headers=headers
        )
        assert replaced.status_code == 200, replaced.text
        assert owner.get(first_url).status_code == 404
        assert owner.get(replaced.headers["Location"]).status_code == 200
        from datetime import timedelta
        from uuid import UUID

        from sqlalchemy.orm import Session

        from vibicle_api.clean_images import cleanup
        from vibicle_api.models import VehicleImage
        from vibicle_api.repositories.auth import clock
        from vibicle_api.repositories.images import ImageStorage

        old_id, active_id = (
            UUID(url.rsplit("/", 1)[-1]) for url in (first_url, replaced.headers["Location"])
        )
        vehicle_id = UUID(created["id"])
        with Session(auth_engine) as db:
            old = db.get(VehicleImage, old_id)
            assert old is not None
            old.created_at = old.updated_at = clock(db) - timedelta(hours=2)
            db.commit()
            storage = ImageStorage(tmp_path)
            assert cleanup(storage, db, vehicle_id, old_id)
            assert not cleanup(storage, db, vehicle_id, active_id)
            assert not storage.path(old_id).exists() and storage.path(active_id).exists()


def test_jpeg_orientation_and_gps_removed() -> None:
    from vibicle_api.image_worker import normalize

    original = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    exif[271] = "Synthetic camera"
    exif[34853] = {1: "N", 2: (25, 1, 2)}
    Image.new("RGB", (24, 16), "green").save(original, format="JPEG", exif=exif)
    size, result = normalize(original.getvalue(), "JPEG")
    assert size == (16, 24)
    with Image.open(BytesIO(result)) as output:
        assert not output.getexif()
        assert "exif" not in output.info


def test_animated_webp_and_overlong_png_rejected() -> None:
    from vibicle_api.image_worker import ImageRejected, normalize

    animated = BytesIO()
    Image.new("RGB", (16, 16), "white").save(
        animated, format="WEBP", save_all=True, append_images=[Image.new("RGB", (16, 16), "blue")]
    )
    with pytest.raises(ImageRejected, match="IMAGE_FRAMES_UNSUPPORTED"):
        normalize(animated.getvalue(), "WEBP")
    tall = BytesIO()
    Image.new("RGB", (8, 6001), "white").save(tall, format="PNG")
    with pytest.raises(ImageRejected, match="IMAGE_DIMENSIONS_INVALID"):
        normalize(tall.getvalue(), "PNG")


def test_upload_three_formats_and_size_bound(
    auth_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_IMAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with client_for(auth_engine) as owner:
        email, csrf = register(owner)
        csrf = sign_in(owner, email, csrf).json()["data"]["csrf_token"]
        headers = {**SOURCE, "x-csrf-token": csrf}
        created = owner.post("/api/vehicles", json=vehicle_payload(), headers=headers).json()[
            "data"
        ]
        path = "/api/vehicles/" + created["id"] + "/image"
        limit = 5 * 1024 * 1024
        oversized = owner.post(
            path,
            headers=headers,
            data={"expected_row_version": "1"},
            files={"file": ("too-large.png", png().ljust(limit + 1, b"\x00"), "image/png")},
        )
        assert oversized.status_code == 413
        for revision, (media, format) in enumerate(
            (("image/png", "PNG"), ("image/jpeg", "JPEG"), ("image/webp", "WEBP")),
            start=1,
        ):
            buffer = BytesIO()
            Image.new("RGB", (32, 16), "green").save(buffer, format=format)
            source = buffer.getvalue()
            if revision == 1:
                source = source.ljust(limit, b"\x00")
            uploaded = owner.post(
                path,
                headers=headers,
                data={"expected_row_version": str(revision)},
                files={"file": ("synthetic", source, media)},
            )
            assert uploaded.status_code == 200, uploaded.text
            delivered = owner.get(uploaded.headers["Location"])
            assert delivered.headers["Content-Type"] == media and len(delivered.content) <= limit
