from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from vibicle_api.config import get_settings
from vibicle_api.errors import reject
from vibicle_api.http_contract import json_body, no_body, one_header, query, success_meta
from vibicle_api.schemas import (
    Credentials,
    CsrfData,
    IdentityResponse,
    LoginData,
    Registration,
    RegistrationData,
    SessionMeta,
    Success,
)
from vibicle_api.services.auth import AuthService, Identity
from vibicle_api.services.identity import (
    cookie_hash,
    decode_token,
    set_session_cookie,
    verify_source,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def auth_service(request: Request) -> AuthService:
    service: AuthService = request.app.state.auth
    return service


async def gate(request: Request, scope: str) -> None:
    secret = get_settings().rate_limit_secret
    if secret is None or len(secret.get_secret_value()) < 32:
        reject(503, "STORE_UNAVAILABLE", "尚未配置限流服務。")
    if request.client is None:
        reject(403, "SOURCE_NOT_ALLOWED", "無法辨識來源。")
    await run_in_threadpool(
        auth_service(request).rate_gate,
        scope,
        request.client.host,
        secret.get_secret_value().encode("utf-8"),
    )


def csrf_header(request: Request) -> bytes | None:
    return decode_token(one_header(request, "x-csrf-token"))


async def require_identity(request: Request, *, mutation: bool = False) -> Identity:
    if mutation:
        verify_source(request, get_settings().public_origin)
    token = cookie_hash(request)
    csrf = csrf_header(request) if mutation else None
    return await run_in_threadpool(auth_service(request).authorize, token, csrf, mutation=mutation)


@router.get("/csrf")
async def csrf_context(request: Request, response: Response) -> Success[CsrfData]:
    verify_source(request, get_settings().public_origin)
    token = cookie_hash(request)
    await gate(request, "csrf_context")
    query(request)
    await no_body(request)
    data, raw = await run_in_threadpool(auth_service(request).bootstrap, token)
    if raw is not None:
        set_session_cookie(response, raw, 900)
    session = SessionMeta(activity="not_touched") if data.context_type == "authenticated" else None
    return Success(data=data, meta=success_meta(request, session=session))


@router.post("/register", status_code=201)
async def register(request: Request) -> Success[RegistrationData]:
    verify_source(request, get_settings().public_origin)
    token = cookie_hash(request)
    csrf = csrf_header(request)
    await gate(request, "register")
    service = auth_service(request)
    checked = await run_in_threadpool(service.check_context, token, csrf, preauth=True)
    query(request)
    credentials = await json_body(request, Registration, 8192)
    await run_in_threadpool(service.register, checked, csrf, credentials)
    return Success(data=RegistrationData(), meta=success_meta(request, "committed"))


@router.post("/login")
async def login(request: Request, response: Response) -> Success[LoginData]:
    verify_source(request, get_settings().public_origin)
    token = cookie_hash(request)
    csrf = csrf_header(request)
    await gate(request, "login")
    service = auth_service(request)
    checked = await run_in_threadpool(service.check_context, token, csrf)
    query(request)
    credentials = await json_body(request, Credentials, 8192)
    data, raw = await run_in_threadpool(service.login, checked, csrf, credentials)
    set_session_cookie(response, raw, 28800)
    return Success(
        data=data, meta=success_meta(request, "committed", SessionMeta(activity="not_touched"))
    )


@router.post("/logout", status_code=204, response_class=Response)
async def logout(request: Request) -> Response:
    verify_source(request, get_settings().public_origin)
    token = cookie_hash(request)
    csrf = csrf_header(request)
    query(request)
    await no_body(request)
    await run_in_threadpool(auth_service(request).logout, token, csrf)
    response = Response(status_code=204)
    set_session_cookie(response, "", 0)
    return response


@router.get("/me", response_model=IdentityResponse)
async def get_current_user(request: Request) -> IdentityResponse:
    query(request)
    token = cookie_hash(request)
    await no_body(request)
    data = await run_in_threadpool(auth_service(request).current_user, token)
    session = SessionMeta(activity="not_touched") if data.authenticated else None
    return IdentityResponse(data=data, meta=success_meta(request, session=session))
