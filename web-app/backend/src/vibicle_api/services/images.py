import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from threading import BoundedSemaphore
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Engine, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from vibicle_api.errors import ContractError, reject
from vibicle_api.models import Vehicle, VehicleImage
from vibicle_api.repositories.auth import clock
from vibicle_api.repositories.images import ImageStorage, image_ref
from vibicle_api.repositories.vehicles import owned_vehicle
from vibicle_api.schemas import ContractModel
from vibicle_api.services.auth import commit
from vibicle_api.services.vehicles import advance_revision, check_revision
from vibicle_api.upload import FILE_LIMIT, MEDIA_FORMATS, Upload
from vibicle_api.vehicle_schemas import ImageRef

IMAGE_SLOT = BoundedSemaphore(1)
LEASE = timedelta(minutes=2)
WORKER_ERRORS = {
    "IMAGE_MEDIA_TYPE_MISMATCH": (415, "照片內容與宣告格式不一致。"),
    "IMAGE_DECODE_FAILED": (422, "無法解碼照片。"),
    "IMAGE_DIMENSIONS_INVALID": (422, "照片尺寸超過限制。"),
    "IMAGE_FRAMES_UNSUPPORTED": (422, "只支援單張靜態照片。"),
    "IMAGE_PROCESSING_LIMIT": (422, "照片處理超過資源限制。"),
    "IMAGE_OUTPUT_TOO_LARGE": (422, "處理後照片大於 5 MiB。"),
}


class ImageMutation(ContractModel):
    image: ImageRef
    status: str = "ready"
    vehicle_row_version: str
    changed: bool = True


def process_image(upload: Upload) -> tuple[int, int, bytes]:
    # Strip inherited application secrets. On Windows SystemRoot may be needed by the loader.
    child_env = {key: os.environ[key] for key in ("SystemRoot", "SYSTEMROOT") if key in os.environ}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "vibicle_api.image_worker", MEDIA_FORMATS[upload.media_type]],
            input=upload.content,
            capture_output=True,
            env=child_env,
            timeout=5,
            check=True,
        )
        head, separator, data = result.stdout.partition(b"\n")
        if not separator or len(head) > 512:
            raise ValueError("Invalid worker output")
        info = json.loads(head)
        if info.get("error") in WORKER_ERRORS:
            code = info["error"]
            status, message = WORKER_ERRORS[code]
            reject(status, code, message)
        width, height = int(info["width"]), int(info["height"])
        if not (1 <= width <= 6000 and 1 <= height <= 6000 and width * height <= 12000000):
            raise ValueError("Invalid dimensions")
        if not 1 <= len(data) <= FILE_LIMIT:
            raise ValueError("Invalid output size")
        return width, height, data
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
        reject(422, "IMAGE_PROCESSING_LIMIT", "照片處理超過限制或未能完成。")


class ImageService:
    def __init__(self, engine: Engine, storage: ImageStorage) -> None:
        self.engine = engine
        self.storage = storage

    def check_owner(self, owner: UUID, vehicle_id: UUID) -> None:
        with Session(self.engine) as db:
            owned_vehicle(db, owner, vehicle_id)

    def upload(self, owner: UUID, vehicle_id: UUID, upload: Upload) -> ImageMutation:
        image_id, work = uuid4(), uuid4()
        with Session(self.engine) as db:
            vehicle = owned_vehicle(db, owner, vehicle_id)
            check_revision(vehicle, upload.expected)
            now = clock(db)
            db.add(
                VehicleImage(
                    id=image_id,
                    vehicle_id=vehicle_id,
                    expected_vehicle_version=vehicle.row_version,
                    status="pending",
                    work_token=work,
                    lease_expires_at=now + LEASE,
                    created_at=now,
                    updated_at=now,
                )
            )
            commit(db)
        try:
            with Session(self.engine) as db:
                image = db.get(VehicleImage, image_id, with_for_update=True)
                now = clock(db)
                if not image or not self.claim(image, work, "pending", now):
                    reject(503, "IMAGE_UNAVAILABLE", "照片處理工作已失效。")
                image.status = "processing"
                image.updated_at = now
                commit(db)
            width, height, data = process_image(upload)
            self.storage.write(image_id, data)
            with Session(self.engine) as db:
                vehicle = owned_vehicle(db, owner, vehicle_id, locked=True)
                check_revision(vehicle, upload.expected)
                image = db.get(VehicleImage, image_id, with_for_update=True)
                now = clock(db)
                if not image or not self.claim(image, work, "processing", now):
                    reject(503, "IMAGE_UNAVAILABLE", "照片處理工作已失效。")
                image.status = "ready"
                image.media_type = upload.media_type
                image.width_px, image.height_px, image.byte_size = width, height, len(data)
                image.processed_at = image.updated_at = now
                image.work_token = image.lease_expires_at = None
                db.flush()
                vehicle.current_image_id = image_id
                advance_revision(db, vehicle)
                result = ImageMutation(
                    image=image_ref(image), vehicle_row_version=str(vehicle.row_version)
                )
                commit(db)
                return result
        except ContractError as error:
            if error.error.outcome == "not_applied":
                self.fail(image_id, work, error.error.code)
            raise

    @staticmethod
    def claim(image: VehicleImage, token: UUID, status: str, now: datetime) -> bool:
        return (
            image.status == status
            and image.work_token == token
            and image.lease_expires_at is not None
            and image.lease_expires_at > now
        )

    def fail(self, image_id: UUID, work: UUID, code: str) -> None:
        try:
            with Session(self.engine) as db:
                image = db.get(VehicleImage, image_id, with_for_update=True)
                if image and image.work_token == work and image.status in {"pending", "processing"}:
                    image.status = "failed"
                    image.last_error_code = code
                    image.updated_at = clock(db)
                    image.work_token = image.lease_expires_at = None
                    commit(db)
        except (SQLAlchemyError, ContractError):
            # Keep the original result. An abandoned lease is handled by maintenance cleanup.
            pass

    def authorize_read(
        self,
        vehicle_id: UUID,
        image_id: UUID,
        owner: UUID | None,
    ) -> ImageRef:
        with Session(self.engine) as db:
            visibility: ColumnElement[bool] = Vehicle.is_listed.is_(True)
            if owner is not None:
                visibility = or_(visibility, Vehicle.owner_user_id == owner)
            image = db.scalar(
                select(VehicleImage)
                .join(
                    Vehicle,
                    (Vehicle.id == VehicleImage.vehicle_id)
                    & (Vehicle.current_image_id == VehicleImage.id),
                )
                .where(
                    Vehicle.id == vehicle_id,
                    VehicleImage.id == image_id,
                    VehicleImage.status == "ready",
                    visibility,
                )
            )
            if image is None:
                reject(404, "RESOURCE_NOT_FOUND", "找不到此照片。")
            return image_ref(image)
