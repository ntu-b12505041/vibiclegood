from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from vibicle_api.models import MaintenanceEvent, MaintenanceRecordVersion

Event = MaintenanceEvent
Version = MaintenanceRecordVersion


def effective_versions(vehicle_id: UUID) -> Select[tuple[MaintenanceRecordVersion]]:
    return (
        select(Version)
        .join(Event, (Event.id == Version.event_id) & (Event.current_version_id == Version.id))
        .where(Event.vehicle_id == vehicle_id)
    )


def highest_effective_mileage(db: Session, vehicle_id: UUID) -> int:
    effective = effective_versions(vehicle_id).subquery()
    highest: int | None = db.scalar(select(func.max(effective.c.mileage_km)))
    return highest or 0
