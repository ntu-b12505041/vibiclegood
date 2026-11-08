import re
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, Field

from vibicle_api.schemas import ContractModel
from vibicle_api.vehicle_schemas import TAIPEI, Mileage, Reason, stripped

SOURCE_LABEL = "車主自行申報・未經機構驗證"
SUBMITTER_LABEL = "車主自行申報"


def maintenance_day(value: object) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Expected YYYY-MM-DD")
    day = date.fromisoformat(value)
    if not date(1900, 1, 1) <= day <= datetime.now(TAIPEI).date():
        raise ValueError("Date out of range")
    return day


def version_uuid(value: object) -> UUID:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ):
        raise ValueError("Expected UUID")
    return UUID(value)


class MaintenanceCreate(ContractModel):
    maintenance_date: Annotated[date, BeforeValidator(maintenance_day)]
    mileage_km: Mileage
    description: Annotated[str, BeforeValidator(stripped), Field(min_length=1, max_length=2000)]


class MaintenanceCorrection(MaintenanceCreate):
    expected_current_version_id: Annotated[UUID, BeforeValidator(version_uuid)]
    correction_reason: Reason


class EventMutation(ContractModel):
    event: dict[str, object]
    vehicle_row_version: str
    created_version_id: UUID
