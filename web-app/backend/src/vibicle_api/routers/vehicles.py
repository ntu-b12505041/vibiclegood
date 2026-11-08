import re
from uuid import UUID

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from vibicle_api.errors import reject
from vibicle_api.http_contract import json_body, no_body, query, success_meta
from vibicle_api.routers.auth import auth_service, require_identity
from vibicle_api.schemas import Success
from vibicle_api.services.auth import Identity
from vibicle_api.services.vehicles import VehicleService
from vibicle_api.vehicle_schemas import (
    ListingChange,
    Page,
    VehicleCard,
    VehicleCreate,
    VehicleMutation,
    VehicleOwner,
    VehiclePatch,
    VehiclePublic,
)

router = APIRouter(prefix="/api", tags=["vehicles"])


def vehicle_service(request: Request) -> VehicleService:
    return VehicleService(auth_service(request).engine)


def parse_uuid(value: str) -> UUID:
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
        reject(422, "VALIDATION_FAILED", "識別碼格式不正確。")
    return UUID(value)


def page_number(params: dict[str, str]) -> int:
    value = params.get("page", "1")
    if not re.fullmatch(r"[0-9]{1,10}", value) or not 1 <= int(value) <= 2147483647:
        reject(422, "VALIDATION_FAILED", "頁碼不正確。", field="page")
    return int(value)


async def touched[T](
    request: Request, identity: Identity, data: T, outcome: str = "read_only"
) -> Success[T]:
    session = await run_in_threadpool(auth_service(request).touch, identity.session_hash)
    return Success(data=data, meta=success_meta(request, outcome, session))


@router.get("/me/vehicles")
async def garage(request: Request) -> Success[Page[VehicleOwner]]:
    identity = await require_identity(request)
    page = page_number(query(request, ("page",)))
    await no_body(request)
    data = await run_in_threadpool(vehicle_service(request).garage, identity.user_id, page)
    return await touched(request, identity, data)


@router.post("/vehicles", status_code=201)
async def create_vehicle(request: Request, response: Response) -> Success[VehicleOwner]:
    identity = await require_identity(request, mutation=True)
    query(request)
    payload = await json_body(request, VehicleCreate)
    data = await run_in_threadpool(vehicle_service(request).create, identity.user_id, payload)
    response.headers["Location"] = f"/api/me/vehicles/{data.id}"
    return await touched(request, identity, data, "committed")


@router.get("/me/vehicles/{vehicle_id}")
async def owner_detail(request: Request, vehicle_id: str) -> Success[VehicleOwner]:
    identity = await require_identity(request)
    query(request)
    await no_body(request)
    data = await run_in_threadpool(
        vehicle_service(request).detail,
        identity.user_id,
        parse_uuid(vehicle_id),
    )
    return await touched(request, identity, data)


@router.patch("/vehicles/{vehicle_id}")
async def patch_vehicle(request: Request, vehicle_id: str) -> Success[VehicleMutation]:
    identity = await require_identity(request, mutation=True)
    query(request)
    payload = await json_body(request, VehiclePatch)
    data = await run_in_threadpool(
        vehicle_service(request).patch,
        identity.user_id,
        parse_uuid(vehicle_id),
        payload,
    )
    return await touched(request, identity, data, "committed" if data.changed else "unchanged")


@router.put("/vehicles/{vehicle_id}/listing")
async def change_listing(request: Request, vehicle_id: str) -> Success[VehicleMutation]:
    identity = await require_identity(request, mutation=True)
    query(request)
    payload = await json_body(request, ListingChange)
    data = await run_in_threadpool(
        vehicle_service(request).listing,
        identity.user_id,
        parse_uuid(vehicle_id),
        payload,
    )
    return await touched(request, identity, data, "committed" if data.changed else "unchanged")


@router.get("/marketplace/vehicles")
async def marketplace(request: Request) -> Success[Page[VehicleCard]]:
    params = query(request, ("page", "q"))
    await no_body(request)
    term = params.get("q", "").strip()
    if len(term) > 50 or "\x00" in term:
        reject(422, "VALIDATION_FAILED", "搜尋限 50 個字元。", field="q")
    data = await run_in_threadpool(vehicle_service(request).market, term, page_number(params))
    return Success(data=data, meta=success_meta(request))


@router.get("/vehicles/{vehicle_id}")
async def public_vehicle(request: Request, vehicle_id: str) -> Success[VehiclePublic]:
    query(request)
    await no_body(request)
    data = await run_in_threadpool(
        vehicle_service(request).public_detail,
        parse_uuid(vehicle_id),
    )
    return Success(data=data, meta=success_meta(request))
