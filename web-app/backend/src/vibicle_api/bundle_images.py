"""Maintenance tooling for a private image bundle with all writers stopped."""

import argparse
import tarfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine
from vibicle_api.models import Vehicle, VehicleImage
from vibicle_api.repositories.images import ImageStorage
from vibicle_api.upload import FILE_LIMIT


def canonical_name(name: str) -> bool:
    try:
        return str(UUID(name)) == name
    except ValueError:
        return False


def pack(root: Path, archive: Path) -> None:
    with tarfile.open(archive, mode="x") as bundle:
        for path in sorted(root.iterdir()):
            if canonical_name(path.name) and path.is_file() and not path.is_symlink():
                bundle.add(path, arcname=path.name, recursive=False)


def unpack(root: Path, archive: Path) -> None:
    if any(root.iterdir()):
        raise RuntimeError("Restore requires an empty private image volume.")
    with tarfile.open(archive, mode="r:") as bundle:
        storage = ImageStorage(root)
        for item in bundle:
            if (
                not canonical_name(item.name)
                or not item.isfile()
                or not 1 <= item.size <= FILE_LIMIT
            ):
                raise RuntimeError("Invalid image bundle member.")
            if storage.path(UUID(item.name)).exists():
                raise RuntimeError("Duplicate image in bundle.")
            contents = bundle.extractfile(item)
            if contents is None:
                raise RuntimeError("Unreadable image bundle member.")
            with contents:
                storage.write(UUID(item.name), contents.read(FILE_LIMIT + 1))


def verify(root: Path) -> None:
    engine = make_engine(get_settings())
    storage = ImageStorage(root)
    try:
        with Session(engine) as db:
            current = db.execute(
                select(VehicleImage.id, VehicleImage.status, VehicleImage.byte_size)
                .select_from(Vehicle)
                .join(VehicleImage, Vehicle.current_image_id == VehicleImage.id)
            ).all()
            for image_id, status, size in current:
                if status != "ready" or size is None:
                    raise RuntimeError("Invalid current image metadata.")
                storage.available(image_id, size)
            print(f"Verified {len(current)} current image files.")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("pack", "unpack", "verify"))
    parser.add_argument("archive", type=Path, nargs="?")
    args = parser.parse_args()
    root = get_settings().private_image_root
    if args.operation == "verify":
        verify(root)
    elif args.archive is None:
        parser.error("Archive path is required.")
    elif args.operation == "pack":
        pack(root, args.archive)
    else:
        unpack(root, args.archive)


if __name__ == "__main__":
    main()
