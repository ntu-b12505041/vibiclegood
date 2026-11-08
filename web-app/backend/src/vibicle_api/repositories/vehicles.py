from typing import cast
from uuid import UUID

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from vibicle_api.errors import reject
from vibicle_api.models import MaintenanceEvent, Vehicle, VehicleImage, VehicleMileageChange


def vehicle_projection() -> Select[tuple[Vehicle, VehicleImage | None, int, bool]]:
    count = (
        select(func.count())
        .select_from(MaintenanceEvent)
        .where(MaintenanceEvent.vehicle_id == Vehicle.id)
        .correlate(Vehicle)
        .scalar_subquery()
    )
    lowered = (
        exists()
        .where(
            VehicleMileageChange.vehicle_id == Vehicle.id,
            VehicleMileageChange.new_mileage_km < VehicleMileageChange.previous_mileage_km,
        )
        .correlate(Vehicle)
    )
    statement = select(Vehicle, VehicleImage, count, lowered).outerjoin(
        VehicleImage,
        (VehicleImage.id == Vehicle.current_image_id)
        & (VehicleImage.vehicle_id == Vehicle.id)
        & (VehicleImage.status == "ready"),
    )
    # Outer joins may omit the image even though the ORM's inference assumes an entity.
    return cast(Select[tuple[Vehicle, VehicleImage | None, int, bool]], statement)


def vehicle_for_owner(owner: UUID, vehicle_id: UUID) -> Select[tuple[Vehicle]]:
    return select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.owner_user_id == owner)


def owned_vehicle(db: Session, owner: UUID, vehicle_id: UUID, *, locked: bool = False) -> Vehicle:
    statement = vehicle_for_owner(owner, vehicle_id)
    row = db.scalar(statement.with_for_update() if locked else statement)
    if row is None:
        reject(404, "RESOURCE_NOT_FOUND", "找不到此車輛。")
    return row
