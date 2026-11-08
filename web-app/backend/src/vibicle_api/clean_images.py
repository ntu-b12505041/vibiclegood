"""Maintenance command. Run only while every API writer is stopped."""

import argparse
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine
from vibicle_api.models import Vehicle, VehicleImage
from vibicle_api.repositories.auth import clock
from vibicle_api.repositories.images import ImageStorage
from vibicle_api.services.auth import commit


def cleanup(storage: ImageStorage, db: Session, vehicle_id: UUID, image_id: UUID) -> bool:
    vehicle = db.get(Vehicle, vehicle_id, with_for_update=True)
    image = db.get(VehicleImage, image_id, with_for_update=True)
    now = clock(db)
    if (
        not vehicle
        or not image
        or vehicle.current_image_id == image_id
        or image.status == "deleted"
        or image.updated_at > now - timedelta(hours=1)
        or (image.lease_expires_at is not None and image.lease_expires_at > now)
    ):
        db.rollback()
        return False
    token = uuid4()
    image.status = "deleting"
    image.work_token, image.lease_expires_at = token, now + timedelta(minutes=2)
    image.updated_at = now
    commit(db)
    try:
        storage.path(image_id).unlink(missing_ok=True)
        for staged in storage.root.glob(f"{image_id}.*.tmp"):
            if staged.is_file() and not staged.is_symlink():
                staged.unlink()
    except OSError:
        return False
    image = db.get(VehicleImage, image_id, populate_existing=True, with_for_update=True)
    now = clock(db)
    if (
        not image
        or image.status != "deleting"
        or image.work_token != token
        or image.lease_expires_at is None
        or image.lease_expires_at <= now
    ):
        db.rollback()
        return False
    image.status = "deleted"
    image.deleted_at = image.updated_at = now
    image.work_token = image.lease_expires_at = None
    commit(db)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    args = parser.parse_args()
    if not args.writers_stopped:
        parser.error("Stop all API writers before cleanup.")
    settings = get_settings()
    engine = make_engine(settings)
    storage = ImageStorage(settings.private_image_root)
    try:
        with Session(engine) as db:
            now = clock(db)
            candidates = db.execute(
                select(VehicleImage.vehicle_id, VehicleImage.id)
                .where(
                    VehicleImage.status != "deleted",
                    VehicleImage.updated_at <= now - timedelta(hours=1),
                    or_(
                        VehicleImage.lease_expires_at.is_(None),
                        VehicleImage.lease_expires_at <= now,
                    ),
                )
                .order_by(VehicleImage.updated_at)
                .limit(200)
            ).all()
            db.rollback()
            count = sum(cleanup(storage, db, v, i) for v, i in candidates)
        print(f"Image cleanup: {count} noncurrent candidates deleted.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
