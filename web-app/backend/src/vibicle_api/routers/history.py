from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from vibicle_api.errors import reject
from vibicle_api.history_schemas import EventMutation, MaintenanceCorrection, MaintenanceCreate
from vibicle_api.http_contract import json_body, no_body, query, success_meta
from vibicle_api.routers.auth import auth_service, require_identity
from vibicle_api.routers.vehicles import page_number, parse_uuid, touched
from vibicle_api.schemas import Success
from vibicle_api.services.history import HistoryKind, HistoryService
from vibicle_api.vehicle_schemas import Page, revision_number

router = APIRouter(prefix="/api", tags=["vehicle history"])
HistoryResponse = Success[Page[dict[str, object]]]


def history_service(request: Request) -> HistoryService:
    return HistoryService(auth_service(request).engine)


@router.post("/vehicles/{vehicle_id}/maintenance-events", status_code=201)
async def create_maintenance(request: Request, vehicle_id: str) -> Success[EventMutation]:
    identity = await require_identity(request, mutation=True)
    query(request)
    payload = await json_body(request, MaintenanceCreate)
    result = await run_in_threadpool(
        history_service(request).record,
        identity.user_id,
        parse_uuid(vehicle_id),
        payload,
    )
    return await touched(request, identity, result, "committed")


@router.post("/vehicles/{vehicle_id}/maintenance-events/{event_id}/corrections", status_code=201)
async def correct_maintenance(
    request: Request,
    vehicle_id: str,
    event_id: str,
) -> Success[EventMutation]:
    identity = await require_identity(request, mutation=True)
    query(request)
    payload = await json_body(request, MaintenanceCorrection)
    result = await run_in_threadpool(
        history_service(request).record,
        identity.user_id,
        parse_uuid(vehicle_id),
        payload,
        parse_uuid(event_id),
    )
    return await touched(request, identity, result, "committed")


async def read_history(
    request: Request,
    vehicle_id: str,
    kind: HistoryKind,
    *,
    owner: bool,
    event_id: str | None = None,
) -> HistoryResponse:
    identity = await require_identity(request) if owner else None
    params = query(request, ("page", "snapshot_row_version"))
    await no_body(request)
    page = page_number(params)
    revision = params.get("snapshot_row_version")
    try:
        snapshot = revision_number(revision) if revision is not None else None
    except ValueError:
        reject(422, "VALIDATION_FAILED", "履歷版本格式不正確。", field="snapshot_row_version")
    if page > 1 and snapshot is None:
        reject(422, "VALIDATION_FAILED", "翻頁時必須提供履歷版本。", field="snapshot_row_version")
    result = await run_in_threadpool(
        history_service(request).read,
        parse_uuid(vehicle_id),
        kind,
        page,
        snapshot,
        identity.user_id if identity else None,
        parse_uuid(event_id) if event_id is not None else None,
    )
    if identity:
        return await touched(request, identity, result)
    return Success(data=result, meta=success_meta(request))


@router.get("/me/vehicles/{vehicle_id}/maintenance-events")
async def owner_timeline(request: Request, vehicle_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "timeline", owner=True)


@router.get("/me/vehicles/{vehicle_id}/maintenance-events/{event_id}/versions")
async def owner_versions(request: Request, vehicle_id: str, event_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "versions", owner=True, event_id=event_id)


@router.get("/me/vehicles/{vehicle_id}/mileage-changes")
async def owner_mileage(request: Request, vehicle_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "mileage", owner=True)


@router.get("/vehicles/{vehicle_id}/maintenance-events")
async def public_timeline(request: Request, vehicle_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "timeline", owner=False)


@router.get("/vehicles/{vehicle_id}/maintenance-events/{event_id}/versions")
async def public_versions(request: Request, vehicle_id: str, event_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "versions", owner=False, event_id=event_id)


@router.get("/vehicles/{vehicle_id}/mileage-changes")
async def public_mileage(request: Request, vehicle_id: str) -> HistoryResponse:
    return await read_history(request, vehicle_id, "mileage", owner=False)
