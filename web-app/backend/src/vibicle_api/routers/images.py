from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from vibicle_api.config import get_settings
from vibicle_api.errors import reject
from vibicle_api.http_contract import bounded_body, no_body, one_header, query
from vibicle_api.repositories.images import ImageStorage
from vibicle_api.routers.auth import auth_service, require_identity
from vibicle_api.routers.vehicles import parse_uuid, touched
from vibicle_api.schemas import Success
from vibicle_api.services.identity import cookie_hash
from vibicle_api.services.images import IMAGE_SLOT, ImageMutation, ImageService
from vibicle_api.upload import BODY_LIMIT, boundary_for, parse_upload

router = APIRouter(prefix="/api/vehicles", tags=["private image storage"])


def image_service(request: Request) -> ImageService:
    return ImageService(
        auth_service(request).engine, ImageStorage(get_settings().private_image_root)
    )


@router.post("/{vehicle_id}/image")
async def upload_image(
    request: Request,
    response: Response,
    vehicle_id: str,
) -> Success[ImageMutation]:
    identity = await require_identity(request, mutation=True)
    query(request)
    vehicle = parse_uuid(vehicle_id)
    service = image_service(request)
    await run_in_threadpool(service.check_owner, identity.user_id, vehicle)
    boundary = boundary_for(one_header(request, "content-type"))
    if not IMAGE_SLOT.acquire(blocking=False):
        reject(503, "IMAGE_PROCESSOR_BUSY", "照片處理中，請稍後再試。")
    try:
        body = await bounded_body(request, BODY_LIMIT)
        upload = await run_in_threadpool(parse_upload, body, boundary)
        result = await run_in_threadpool(service.upload, identity.user_id, vehicle, upload)
    finally:
        IMAGE_SLOT.release()
    response.headers["Location"] = result.image.url
    return await touched(request, identity, result, "committed")


@router.get("/{vehicle_id}/images/{image_id}", response_class=Response)
async def read_image(request: Request, vehicle_id: str, image_id: str) -> Response:
    query(request)
    await no_body(request)
    vehicle, image = parse_uuid(vehicle_id), parse_uuid(image_id)
    service = image_service(request)
    identity = await run_in_threadpool(auth_service(request).current_user, cookie_hash(request))
    metadata = await run_in_threadpool(
        service.authorize_read,
        vehicle,
        image,
        identity.user.id if identity.user else None,
    )
    if any(
        name in request.headers
        for name in (
            "if-none-match",
            "if-modified-since",
            "if-match",
            "if-unmodified-since",
        )
    ):
        reject(400, "CONDITIONAL_REQUEST_UNSUPPORTED", "此圖片不接受條件式請求。")
    data = await run_in_threadpool(service.storage.read, image, metadata.byte_size)
    return Response(
        data, media_type=metadata.media_type, headers={"X-Content-Type-Options": "nosniff"}
    )
