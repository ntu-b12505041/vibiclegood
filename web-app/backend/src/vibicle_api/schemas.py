from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SessionMeta(ContractModel):
    activity: Literal["not_applicable", "not_touched", "touched", "not_extended", "unknown"] = (
        "not_applicable"
    )
    requires_revalidation: bool = False
    reason: (
        Literal[
            "SESSION_EXPIRED", "SESSION_REVOKED", "SESSION_STORE_UNAVAILABLE", "RECOVERY_REQUIRED"
        ]
        | None
    ) = None


class CurrentUser(ContractModel):
    id: UUID
    email: str


class IdentityData(ContractModel):
    authenticated: bool = False
    user: CurrentUser | None = None
    absolute_expires_at: datetime | None = None


class LoginData(ContractModel):
    authenticated: Literal[True] = True
    user: CurrentUser
    csrf_token: str
    absolute_expires_at: datetime


class CsrfData(ContractModel):
    context_type: Literal["preauth", "authenticated"]
    csrf_token: str
    absolute_expires_at: datetime


class RegistrationData(ContractModel):
    status: Literal["registered"] = "registered"
    next: Literal["manual_login"] = "manual_login"


class Credentials(ContractModel):
    email: str
    password: str = Field(min_length=12, max_length=128)


class Registration(Credentials):
    password_confirmation: str = Field(min_length=12, max_length=128)


class SuccessMeta(ContractModel):
    request_id: UUID
    business_outcome: str = "read_only"
    session: SessionMeta


class Success[Data](ContractModel):
    data: Data
    meta: SuccessMeta


IdentityResponse = Success[IdentityData]


class ErrorData(ContractModel):
    code: str
    message: str
    outcome: Literal["not_applied", "unknown"] = "not_applied"
    fields: list[dict[str, str]] = Field(default_factory=list)
    details: dict[str, object] | None = None


class ErrorMeta(ContractModel):
    request_id: UUID
    session: SessionMeta


class ErrorResponse(ContractModel):
    error: ErrorData
    meta: ErrorMeta
