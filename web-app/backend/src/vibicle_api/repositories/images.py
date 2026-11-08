import os
from pathlib import Path
from uuid import UUID, uuid4

from vibicle_api.errors import reject
from vibicle_api.models import VehicleImage
from vibicle_api.vehicle_schemas import ImageRef


def image_ref(row: VehicleImage) -> ImageRef:
    assert row.media_type and row.byte_size and row.width_px and row.height_px and row.processed_at
    return ImageRef(
        id=row.id,
        url=f"/api/vehicles/{row.vehicle_id}/images/{row.id}",
        media_type=row.media_type,
        byte_size=row.byte_size,
        width_px=row.width_px,
        height_px=row.height_px,
        processed_at=row.processed_at,
    )


class ImageStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, image_id: UUID) -> Path:
        return self.root / str(image_id)

    def write(self, image_id: UUID, data: bytes) -> None:
        final = self.path(image_id)
        temporary = self.root / f"{image_id}.{uuid4()}.tmp"
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with temporary.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, final)
            if os.name == "posix":
                directory = os.open(self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except OSError:
            reject(503, "IMAGE_UNAVAILABLE", "無法儲存照片。")
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # The maintenance cleaner can remove abandoned temporary bytes.

    def available(self, image_id: UUID, expected: int) -> None:
        path = self.path(image_id)
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size != expected:
                raise OSError("Storage mismatch")
        except OSError:
            reject(503, "IMAGE_UNAVAILABLE", "照片儲存目前無法使用。")

    def read(self, image_id: UUID, expected: int) -> bytes:
        self.available(image_id, expected)
        try:
            with self.path(image_id).open("rb") as photo:
                data = photo.read(expected + 1)
            if len(data) != expected:
                raise OSError("Storage mismatch")
            return data
        except OSError:
            reject(503, "IMAGE_UNAVAILABLE", "照片目前無法讀取。")
