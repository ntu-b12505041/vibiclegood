import pytest
from pydantic import ValidationError

from vibicle_api.history_schemas import MaintenanceCreate
from vibicle_api.schemas import Credentials
from vibicle_api.vehicle_schemas import VehiclePatch


@pytest.mark.parametrize("value", [True, 80000.0, "80000", None, -1, 2_000_001])
def test_mileage_rejects_non_contracted_values(value: object) -> None:
    with pytest.raises(ValidationError):
        VehiclePatch.model_validate({"expected_row_version": "1", "current_mileage_km": value})


@pytest.mark.parametrize("value", ["01", "+1", "9223372036854775808", 1])
def test_revision_requires_canonical_int64_string(value: object) -> None:
    with pytest.raises(ValidationError):
        VehiclePatch.model_validate({"expected_row_version": value, "brand": "Synthetic"})


@pytest.mark.parametrize("size", [11, 12, 128, 129])
def test_password_counts_unicode_codepoints(size: int) -> None:
    password = " " + "😀" * (size - 2) + " "
    data = {"email": "fixture@example.test", "password": password}
    if 12 <= size <= 128:
        assert Credentials.model_validate(data).password == password
    else:
        with pytest.raises(ValidationError):
            Credentials.model_validate(data)


@pytest.mark.parametrize("day", ["1900-01-01T00:00:00Z", "1899-12-31", "2999-01-01", "2020-02-30"])
def test_maintenance_rejects_invalid_calendar_dates(day: str) -> None:
    with pytest.raises(ValidationError):
        MaintenanceCreate.model_validate(
            {"maintenance_date": day, "mileage_km": 0, "description": "synthetic"}
        )
