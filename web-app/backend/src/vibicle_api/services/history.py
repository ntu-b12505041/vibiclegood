from collections.abc import Mapping
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Engine, Select, exists, func, select, true
from sqlalchemy.orm import Session

from vibicle_api.errors import reject
from vibicle_api.history_schemas import (
    SOURCE_LABEL,
    SUBMITTER_LABEL,
    EventMutation,
    MaintenanceCorrection,
    MaintenanceCreate,
)
from vibicle_api.models import MaintenanceEvent as Event
from vibicle_api.models import MaintenanceRecordVersion as Version
from vibicle_api.models import Vehicle
from vibicle_api.models import VehicleMileageChange as Ledger
from vibicle_api.repositories.history import effective_versions
from vibicle_api.repositories.vehicles import owned_vehicle
from vibicle_api.services.auth import commit
from vibicle_api.services.vehicles import advance_revision
from vibicle_api.vehicle_schemas import Page, make_page

HistoryKind = Literal["timeline", "versions", "mileage"]
VERSION_FIELDS = (
    "id",
    "event_id",
    "version_no",
    "previous_version_id",
    "maintenance_date",
    "mileage_km",
    "description",
    "correction_reason",
    "source",
    "submitted_at",
)


def version_projection(row: Mapping[str, object], *, owner: bool) -> dict[str, object]:
    result = {key: row[key] for key in VERSION_FIELDS}
    result.update(
        source_label=SOURCE_LABEL,
        submitter_label=SUBMITTER_LABEL,
        is_effective=row["id"] == row["current_version_id"],
    )
    if owner:
        result["submitted_by_user_id"] = row["submitted_by_user_id"]
    return result


def event_projection(row: Mapping[str, object], *, owner: bool) -> dict[str, object]:
    return {
        "id": row["event_id"],
        "current_version": version_projection(row, owner=owner),
        "version_count": row["version_no"],
    }


def mileage_projection(row: Mapping[str, object], *, owner: bool) -> dict[str, object]:
    result = {
        field: row[field]
        for field in (
            "id",
            "previous_mileage_km",
            "new_mileage_km",
            "reason",
            "created_at",
        )
    }
    if owner:
        result.update(
            actor_user_id=row["actor_user_id"], vehicle_revision=str(row["vehicle_revision"])
        )
    return result


class HistoryService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def read(
        self,
        vehicle_id: UUID,
        kind: HistoryKind,
        page: int,
        snapshot: int | None,
        owner: UUID | None,
        event_id: UUID | None = None,
    ) -> Page[dict[str, object]]:
        visible = select(Vehicle.row_version.label("vehicle_revision_now")).where(
            Vehicle.id == vehicle_id,
            Vehicle.is_listed.is_(True) if owner is None else Vehicle.owner_user_id == owner,
        )
        if kind == "versions":
            visible = visible.where(
                exists().where(Event.id == event_id, Event.vehicle_id == Vehicle.id)
            )
        visibility = visible.cte("visible_vehicle")
        dataset = self.history_query(vehicle_id, kind, owner, event_id).cte("matching_history")
        order: tuple[str, ...]
        if kind == "timeline":
            order = ("maintenance_date", "mileage_km", "submitted_at", "id")
        elif kind == "versions":
            order = ("version_no",)
        else:
            order = ("vehicle_revision",)
        selected = select(dataset)
        if kind == "versions":
            selected = selected.order_by(*(dataset.c[field].asc() for field in order))
        else:
            selected = selected.order_by(*(dataset.c[field].desc() for field in order))
        subset = selected.offset((page - 1) * 20).limit(20).subquery()
        total = select(func.count()).select_from(dataset).scalar_subquery()
        statement = (
            select(visibility.c.vehicle_revision_now, total.label("total_count"), subset)
            .select_from(visibility.outerjoin(subset, true()))
            .order_by(
                *(
                    subset.c[field].asc() if kind == "versions" else subset.c[field].desc()
                    for field in order
                )
            )
        )
        with Session(self.engine) as db:
            results = db.execute(statement).mappings().all()
        if not results:
            reject(404, "RESOURCE_NOT_FOUND", "找不到此車輛或履歷。")
        revision = int(results[0]["vehicle_revision_now"])
        if snapshot is not None and snapshot != revision:
            reject(
                409,
                "COLLECTION_CHANGED",
                "履歷已更新，請從第一頁重新載入。",
                details={"current_row_version": str(revision)},
            )
        project = {
            "timeline": event_projection,
            "versions": version_projection,
            "mileage": mileage_projection,
        }[kind]
        items = [
            project(dict(row), owner=owner is not None) for row in results if row["id"] is not None
        ]
        return make_page(items, page, 20, int(results[0]["total_count"]), revision=revision)

    @staticmethod
    def history_query(
        vehicle_id: UUID,
        kind: HistoryKind,
        owner: UUID | None,
        event_id: UUID | None,
    ) -> Select[tuple[object, ...]]:
        if kind == "mileage":
            ledger = select(*Ledger.__table__.columns).where(Ledger.vehicle_id == vehicle_id)
            if owner is None:
                ledger = ledger.where(Ledger.new_mileage_km < Ledger.previous_mileage_km)
            return ledger
        query = (
            select(*Version.__table__.columns, Event.current_version_id)
            .join(Event, Event.id == Version.event_id)
            .where(Event.vehicle_id == vehicle_id)
        )
        if kind == "versions":
            return query.where(Event.id == event_id)
        return query.where(Version.id == Event.current_version_id)

    def record(
        self,
        owner: UUID,
        vehicle_id: UUID,
        payload: MaintenanceCreate,
        event_id: UUID | None = None,
    ) -> EventMutation:
        with Session(self.engine) as db:
            vehicle = owned_vehicle(db, owner, vehicle_id, locked=True)
            parent: Version | None = None
            next_id = uuid4()
            if event_id is None:
                event = Event(id=uuid4(), vehicle_id=vehicle.id, current_version_id=next_id)
            else:
                event = self.event_for_correction(db, vehicle_id, event_id, payload)
                parent = db.get(Version, event.current_version_id)
                assert parent is not None
            self.check_candidate(db, vehicle, payload, excluding=event_id)
            if parent is None:
                db.add(event)
                db.flush()
            number = parent.version_no + 1 if parent else 1
            if number > 2147483647:
                reject(503, "REVISION_EXHAUSTED", "目前無法新增履歷版本。")
            version = Version(
                id=next_id,
                event_id=event.id,
                version_no=number,
                previous_version_id=parent.id if parent else None,
                maintenance_date=payload.maintenance_date,
                mileage_km=payload.mileage_km,
                description=payload.description,
                submitted_by_user_id=owner,
                correction_reason=payload.correction_reason
                if isinstance(payload, MaintenanceCorrection)
                else None,
            )
            db.add(version)
            event.current_version_id = version.id
            advance_revision(db, vehicle)
            db.flush()
            projection = {key: getattr(version, key) for key in VERSION_FIELDS}
            projection.update(
                submitted_by_user_id=version.submitted_by_user_id,
                current_version_id=version.id,
            )
            result = EventMutation(
                event=event_projection(projection, owner=True),
                vehicle_row_version=str(vehicle.row_version),
                created_version_id=version.id,
            )
            commit(db)
            return result

    @staticmethod
    def event_for_correction(
        db: Session,
        vehicle_id: UUID,
        event_id: UUID,
        payload: MaintenanceCreate,
    ) -> Event:
        event = db.scalar(select(Event).where(Event.id == event_id, Event.vehicle_id == vehicle_id))
        if event is None:
            reject(404, "RESOURCE_NOT_FOUND", "找不到此履歷。")
        assert isinstance(payload, MaintenanceCorrection)
        if payload.expected_current_version_id != event.current_version_id:
            reject(
                409,
                "MAINTENANCE_VERSION_CONFLICT",
                "此履歷已更正，請重讀目前版本。",
                details={
                    "event_id": str(event.id),
                    "current_version_id": str(event.current_version_id),
                },
            )
        return event

    @staticmethod
    def check_candidate(
        db: Session,
        vehicle: Vehicle,
        payload: MaintenanceCreate,
        *,
        excluding: UUID | None,
    ) -> None:
        if payload.mileage_km > vehicle.current_mileage_km:
            reject(
                422,
                "MILEAGE_ABOVE_CURRENT",
                "維修里程不能高於目前申報里程。請先更新目前里程。",
                field="mileage_km",
            )
        query = effective_versions(vehicle.id)
        if excluding is not None:
            query = query.where(Version.event_id != excluding)
        relevant = query.where(Version.maintenance_date != payload.maintenance_date)
        versions = list(db.scalars(relevant))
        earlier = [row for row in versions if row.maintenance_date < payload.maintenance_date]
        later = [row for row in versions if row.maintenance_date > payload.maintenance_date]
        lower = max((row.mileage_km for row in earlier), default=0)
        upper = min((row.mileage_km for row in later), default=vehicle.current_mileage_km)
        if not lower <= payload.mileage_km <= upper:
            conflicts = [
                str(row.event_id) for row in earlier if row.mileage_km > payload.mileage_km
            ] + [str(row.event_id) for row in later if row.mileage_km < payload.mileage_km]
            reject(
                422,
                "MILEAGE_DATE_CONFLICT",
                "維修里程與前後日期的有效履歷衝突。",
                field="mileage_km",
                details={
                    "lower_bound_km": lower,
                    "upper_bound_km": upper,
                    "conflict_event_ids": conflicts[:20],
                },
            )
