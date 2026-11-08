from typing import Never

from vibicle_api.schemas import ErrorData


class ContractError(Exception):
    def __init__(self, status: int, error: ErrorData, *, retry_after: int | None = None) -> None:
        self.status = status
        self.error = error
        self.retry_after = retry_after


def reject(
    status: int,
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: dict[str, object] | None = None,
    retry_after: int | None = None,
) -> Never:
    raise ContractError(
        status,
        ErrorData(
            code=code,
            message=message,
            fields=[{"field": field, "code": code, "message": message}] if field else [],
            details=details,
        ),
        retry_after=retry_after,
    )
