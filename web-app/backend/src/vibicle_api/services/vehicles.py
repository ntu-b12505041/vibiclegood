from uuid import UUID

from sqlalchemy import ColumnElement, Engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vibicle_api.config import get_settings
from vibicle_api.errors import reject
from vibicle_api.models import Vehicle, VehicleImage, VehicleMileageChange
from vibicle_api.repositories.auth import clock
from vibicle_api.repositories.history import highest_effective_mileage
from vibicle_api.repositories.images import ImageStorage, image_ref
from vibicle_api.repositories.vehicles import owned_vehicle, vehicle_projection
from vibicle_api.services.auth import commit
from vibicle_api.vehicle_schemas import (
    MAX_REVISION,
    ListingChange,
    Page,
    VehicleCard,
    VehicleCreate,
    VehicleMutation,
    VehicleOwner,
    VehiclePatch,
    VehiclePublic,
    make_page,
)


def check_revision(vehicle: Vehicle, expected: str) -> None:
    current = str(vehicle.row_version)
    if expected != current:
        reject(
            409,
            "ROW_VERSION_CONFLICT",
            "資料已更新，請重新載入後確認。",
            details={"expected_row_version": expected, "current_row_version": current},
        )


def advance_revision(db: Session, vehicle: Vehicle) -> None:
    if vehicle.row_version >= MAX_REVISION:
        reject(503, "REVISION_EXHAUSTED", "目前無法更新這筆資料。")
    vehicle.row_version += 1
    vehicle.updated_at = max(vehicle.updated_at, clock(db))


def owner_projection(
    vehicle: Vehicle,
    image: VehicleImage | None,
    event_count: int,
    lowered: bool,
) -> VehicleOwner:
    return VehicleOwner(
        id=vehicle.id,
        owner_user_id=vehicle.owner_user_id,
        vin=vehicle.vin,
        brand=vehicle.brand,
        model=vehicle.model,
        model_year=vehicle.model_year,
        current_mileage_km=vehicle.current_mileage_km,
        description=vehicle.description,
        price_twd=vehicle.price_twd,
        is_listed=vehicle.is_listed,
        last_listed_at=vehicle.last_listed_at,
        main_image=image_ref(image) if image else None,
        row_version=str(vehicle.row_version),
        effective_event_count=event_count,
        mileage_was_lowered=lowered,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


def public_card(vehicle: Vehicle, image: VehicleImage | None) -> VehicleCard:
    assert vehicle.price_twd is not None and vehicle.last_listed_at is not None
    return VehicleCard(
        id=vehicle.id,
        vin_suffix=vehicle.vin[-6:],
        brand=vehicle.brand,
        model=vehicle.model,
        model_year=vehicle.model_year,
        current_mileage_km=vehicle.current_mileage_km,
        price_twd=vehicle.price_twd,
        main_image=image_ref(image) if image else None,
        last_listed_at=vehicle.last_listed_at,
    )


def owner_detail(db: Session, owner: UUID, vehicle_id: UUID) -> VehicleOwner:
    record = db.execute(
        vehicle_projection().where(
            Vehicle.id == vehicle_id,
            Vehicle.owner_user_id == owner,
        )
    ).one_or_none()
    if record is None:
        reject(404, "RESOURCE_NOT_FOUND", "找不到此車輛。")
    return owner_projection(*record)


class VehicleService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, owner: UUID, data: VehicleCreate) -> VehicleOwner:
        try:
            with Session(self.engine, expire_on_commit=False) as db:
                row = Vehicle(owner_user_id=owner, **data.model_dump())
                db.add(row)
                db.flush()
                db.add(
                    VehicleMileageChange(
                        vehicle_id=row.id,
                        actor_user_id=owner,
                        new_mileage_km=row.current_mileage_km,
                        vehicle_revision=row.row_version,
                    )
                )
                result = owner_detail(db, owner, row.id)
                commit(db)
                return result
        except IntegrityError as exc:
            name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if name == "uq_vehicles_vin":
                reject(409, "VIN_CONFLICT", "這組 VIN 無法建立。")
            raise

    def garage(self, owner: UUID, page: int) -> Page[VehicleOwner]:
        with Session(self.engine) as db:
            matching = Vehicle.owner_user_id == owner
            total = db.scalar(select(func.count()).select_from(Vehicle).where(matching)) or 0
            items = list(
                db.execute(
                    vehicle_projection()
                    .where(matching)
                    .order_by(Vehicle.created_at.desc(), Vehicle.id.desc())
                    .offset((page - 1) * 20)
                    .limit(20)
                )
            )
            return make_page([owner_projection(*row) for row in items], page, 20, total)

    def detail(self, owner: UUID, vehicle_id: UUID) -> VehicleOwner:
        with Session(self.engine) as db:
            return owner_detail(db, owner, vehicle_id)

    def patch(self, owner: UUID, vehicle_id: UUID, data: VehiclePatch) -> VehicleMutation:
        changes = data.model_dump(
            exclude_unset=True,
            exclude={"expected_row_version", "mileage_change_reason", "mileage_decrease_confirmed"},
        )
        with Session(self.engine) as db:
            row = owned_vehicle(db, owner, vehicle_id, locked=True)
            check_revision(row, data.expected_row_version)
            if not changes:
                reject(422, "EMPTY_PATCH", "請指定要編輯的欄位。")
            previous = row.current_mileage_km
            mileage = data.current_mileage_km if data.current_mileage_km is not None else previous
            self.validate_mileage_change(db, row, previous, mileage, data)
            if row.is_listed and "price_twd" in changes and changes["price_twd"] is None:
                reject(422, "LISTED_PRICE_REQUIRED", "請先下架再清除售價。")
            changed = any(getattr(row, field) != value for field, value in changes.items())
            if changed:
                for field, value in changes.items():
                    setattr(row, field, value)
                advance_revision(db, row)
                if mileage != previous:
                    db.add(
                        VehicleMileageChange(
                            vehicle_id=row.id,
                            actor_user_id=owner,
                            previous_mileage_km=previous,
                            new_mileage_km=mileage,
                            vehicle_revision=row.row_version,
                            reason=data.mileage_change_reason,
                        )
                    )
            result = VehicleMutation(vehicle=owner_detail(db, owner, row.id), changed=changed)
            commit(db)
            return result

    def listing(self, owner: UUID, vehicle_id: UUID, data: ListingChange) -> VehicleMutation:
        with Session(self.engine) as db:
            vehicle = owned_vehicle(db, owner, vehicle_id, locked=True)
            check_revision(vehicle, data.expected_row_version)
            changed = vehicle.is_listed != data.is_listed
            if data.is_listed:
                image = (
                    db.get(VehicleImage, vehicle.current_image_id)
                    if vehicle.current_image_id
                    else None
                )
                if (
                    vehicle.price_twd is None
                    or image is None
                    or image.status != "ready"
                    or image.byte_size is None
                ):
                    reject(422, "LISTING_NOT_READY", "請先設定售價並上傳一張有效的主照片。")
                ImageStorage(get_settings().private_image_root).available(image.id, image.byte_size)
            if changed:
                vehicle.is_listed = data.is_listed
                advance_revision(db, vehicle)
                if data.is_listed:
                    vehicle.last_listed_at = vehicle.updated_at
            result = VehicleMutation(vehicle=owner_detail(db, owner, vehicle.id), changed=changed)
            commit(db)
            return result

    def market(self, query: str, page: int) -> Page[VehicleCard]:
        uppercase, lowercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
        search = query.translate(str.maketrans(uppercase, lowercase))
        visible: list[ColumnElement[bool]] = [Vehicle.is_listed.is_(True)]
        if search:
            visible.append(
                or_(
                    func.translate(Vehicle.brand, uppercase, lowercase).contains(
                        search, autoescape=True
                    ),
                    func.translate(Vehicle.model, uppercase, lowercase).contains(
                        search, autoescape=True
                    ),
                )
            )
        with Session(self.engine) as db:
            total = db.scalar(select(func.count()).select_from(Vehicle).where(*visible)) or 0
            rows = db.execute(
                vehicle_projection()
                .where(*visible)
                .order_by(Vehicle.last_listed_at.desc(), Vehicle.id.desc())
                .offset((page - 1) * 12)
                .limit(12)
            ).all()
            return make_page(
                [public_card(vehicle, image) for vehicle, image, _, _ in rows], page, 12, total
            )

    def public_detail(self, vehicle_id: UUID) -> VehiclePublic:
        with Session(self.engine) as db:
            row = db.execute(
                vehicle_projection().where(
                    Vehicle.id == vehicle_id,
                    Vehicle.is_listed.is_(True),
                )
            ).one_or_none()
            if row is None:
                reject(404, "RESOURCE_NOT_FOUND", "找不到此車輛。")
            vehicle, image, count, lowered = row
            return VehiclePublic(
                **public_card(vehicle, image).model_dump(),
                description=vehicle.description,
                row_version=str(vehicle.row_version),
                effective_event_count=count,
                mileage_was_lowered=lowered,
            )

    @staticmethod
    def validate_mileage_change(
        db: Session,
        row: Vehicle,
        previous: int,
        mileage: int,
        data: VehiclePatch,
    ) -> None:
        decreasing = mileage < previous
        if data.mileage_decrease_confirmed and not decreasing:
            reject(422, "UNEXPECTED_MILEAGE_CONFIRMATION", "只有里程下修需要確認。")
        if data.mileage_change_reason is not None and mileage == previous:
            reject(422, "UNEXPECTED_MILEAGE_REASON", "沒有里程異動，不需填寫理由。")
        if mileage != previous:
            highest = highest_effective_mileage(db, row.id)
            if mileage < highest:
                reject(
                    422,
                    "MILEAGE_BELOW_EFFECTIVE_HISTORY",
                    "目前里程不能低於有效履歷，請先更正履歷。",
                    details={"effective_max_mileage_km": highest},
                )
        if decreasing and data.mileage_change_reason is None:
            reject(422, "MILEAGE_DECREASE_REASON_REQUIRED", "請填寫下修理由。")
        if decreasing and not data.mileage_decrease_confirmed:
            reject(422, "MILEAGE_DECREASE_CONFIRMATION_REQUIRED", "請明確確認下修里程。")
