import re
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from vibicle_api.schemas import ContractModel

TAIPEI = ZoneInfo("Asia/Taipei")
MAX_REVISION = 9223372036854775807


def stripped(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def normalize_vin(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


def year_in_range(value: object) -> object:
    if type(value) is int and value > datetime.now(TAIPEI).year + 1:
        raise ValueError("model_year")
    return value


Brand = Annotated[str, BeforeValidator(stripped), Field(min_length=1, max_length=50)]
Model = Annotated[str, BeforeValidator(stripped), Field(min_length=1, max_length=100)]
Mileage = Annotated[int, Field(ge=0, le=2000000)]
Price = Annotated[int, Field(ge=1, le=100000000)]
ModelYear = Annotated[int, BeforeValidator(year_in_range), Field(ge=1900, le=9999)]
Description = Annotated[str, Field(max_length=2000)]
Reason = Annotated[str, BeforeValidator(stripped), Field(min_length=1, max_length=500)]
Vin = Annotated[str, BeforeValidator(normalize_vin), Field(pattern=r"^[A-HJ-NPR-Z0-9]{17}$")]


def revision_number(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > MAX_REVISION:
        raise ValueError("Invalid revision")
    return int(value)


def canonical_revision(value: str) -> str:
    revision_number(value)
    return value


Revision = Annotated[str, AfterValidator(canonical_revision)]


class VehicleCreate(ContractModel):
    vin: Vin
    brand: Brand
    model: Model
    model_year: ModelYear
    current_mileage_km: Mileage
    description: Description = ""
    price_twd: Price | None = None


class VehiclePatch(ContractModel):
    expected_row_version: Revision
    brand: Brand | None = None
    model: Model | None = None
    model_year: ModelYear | None = None
    current_mileage_km: Mileage | None = None
    description: Description | None = None
    price_twd: Price | None = None
    mileage_change_reason: Reason | None = None
    mileage_decrease_confirmed: bool = False

    @model_validator(mode="after")
    def forbid_explicit_null(self) -> "VehiclePatch":
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in (
                "brand",
                "model",
                "model_year",
                "current_mileage_km",
                "description",
                "mileage_change_reason",
            )
        ):
            raise ValueError("Only price_twd accepts null")
        return self


class ImageRef(ContractModel):
    id: UUID
    url: str
    media_type: str
    byte_size: int
    width_px: int
    height_px: int
    processed_at: datetime


class VehicleOwner(ContractModel):
    id: UUID
    owner_user_id: UUID
    vin: str
    brand: str
    model: str
    model_year: int
    current_mileage_km: int
    description: str
    price_twd: int | None
    is_listed: bool
    last_listed_at: datetime | None
    main_image: ImageRef | None
    row_version: str
    effective_event_count: int
    mileage_was_lowered: bool
    created_at: datetime
    updated_at: datetime


class VehicleMutation(ContractModel):
    vehicle: VehicleOwner
    changed: bool


class ListingChange(ContractModel):
    expected_row_version: Revision
    is_listed: bool


class VehicleCard(ContractModel):
    id: UUID
    vin_suffix: str
    brand: str
    model: str
    model_year: int
    current_mileage_km: int
    price_twd: int
    main_image: ImageRef | None
    last_listed_at: datetime


class VehiclePublic(VehicleCard):
    description: str
    is_listed: bool = True
    row_version: str
    effective_event_count: int
    mileage_was_lowered: bool


class Pagination(ContractModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool


class Page[T](ContractModel):
    items: list[T]
    pagination: Pagination
    vehicle_row_version: str | None = None


def make_page[T](
    items: list[T],
    page: int,
    size: int,
    total: int,
    *,
    revision: int | None = None,
) -> Page[T]:
    pages = (total + size - 1) // size
    return Page(
        items=items,
        vehicle_row_version=str(revision) if revision is not None else None,
        pagination=Pagination(
            page=page,
            page_size=size,
            total_items=total,
            total_pages=pages,
            has_next=page < pages,
        ),
    )
