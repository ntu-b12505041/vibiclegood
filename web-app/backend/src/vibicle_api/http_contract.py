import json
from collections.abc import Iterable
from typing import Never
from uuid import UUID

from fastapi import Request
from pydantic import ValidationError

from vibicle_api.errors import reject
from vibicle_api.schemas import ContractModel, SessionMeta, SuccessMeta


def one_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    if len(values) > 1:
        reject(400, "DUPLICATE_FIELD", "Request Header 重複。")
    return values[0] if values else None


def query(request: Request, allowed: Iterable[str] = ()) -> dict[str, str]:
    params = request.query_params
    if any(len(params.getlist(key)) > 1 for key in params):
        reject(400, "DUPLICATE_FIELD", "Query 欄位重複。")
    if not params.keys() <= set(allowed):
        reject(422, "VALIDATION_FAILED", "Query 欄位不適用。")
    return dict(params)


async def bounded_body(request: Request, limit: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            reject(413, "PAYLOAD_TOO_LARGE", "Request 過大。")
        body.extend(chunk)
    return bytes(body)


async def no_body(request: Request, limit: int = 8192) -> None:
    if await bounded_body(request, limit):
        reject(422, "VALIDATION_FAILED", "此介面不接受 Body。")


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            reject(400, "DUPLICATE_FIELD", "JSON 欄位重複。")
        result[name] = value
    return result


def reject_constant(_: str) -> Never:
    raise ValueError("Non-finite JSON number")


async def json_body[T: ContractModel](request: Request, model: type[T], limit: int = 32768) -> T:
    media_type = one_header(request, "content-type")
    if not media_type or media_type.split(";", 1)[0].strip().lower() != "application/json":
        reject(415, "UNSUPPORTED_MEDIA_TYPE", "請使用 application/json。")
    raw = await bounded_body(request, limit)
    try:
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        # JSON escape sequences may otherwise turn into lone surrogate code points.
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except (ValueError, RecursionError):
        reject(400, "MALFORMED_REQUEST", "JSON 格式不正確。")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        # Report only declared field names, never input, ctx, or arbitrary extra names.
        loc = exc.errors(include_input=False, include_context=False)[0]["loc"]
        field = str(loc[0]) if loc and loc[0] in model.model_fields else None
        reject(422, "VALIDATION_FAILED", "請檢查欄位格式。", field=field)


def success_meta(
    request: Request,
    outcome: str = "read_only",
    session: SessionMeta | None = None,
) -> SuccessMeta:
    return SuccessMeta(
        request_id=UUID(request.state.request_id),
        business_outcome=outcome,
        session=session or SessionMeta(),
    )
