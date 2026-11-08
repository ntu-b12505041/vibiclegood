import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from vibicle_api.config import get_settings
from vibicle_api.database import make_engine
from vibicle_api.errors import ContractError
from vibicle_api.routers.auth import router as auth_router
from vibicle_api.routers.history import router as history_router
from vibicle_api.routers.images import router as image_router
from vibicle_api.routers.vehicles import router as vehicle_router
from vibicle_api.schemas import ErrorData, ErrorMeta, ErrorResponse, SessionMeta
from vibicle_api.services.auth import AuthService
from vibicle_api.services.identity import source_origin


def error_response(request: Request, status: int, error: ErrorData) -> JSONResponse:
    unavailable = error.code in {"STORE_UNAVAILABLE", "COMMIT_OUTCOME_UNKNOWN"}
    body = ErrorResponse(
        error=error,
        meta=ErrorMeta(
            request_id=UUID(request.state.request_id),
            session=SessionMeta(
                activity="unknown" if unavailable else "not_touched",
                requires_revalidation=unavailable,
                reason="SESSION_STORE_UNAVAILABLE" if unavailable else None,
            ),
        ),
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app(engine: Engine | None = None) -> FastAPI:
    settings = get_settings()
    production = settings.api_env == "production"
    if production and (
        source_origin(settings.public_origin, referer=False) is None
        or not settings.public_origin.startswith("https://")
    ):
        raise RuntimeError("Production requires a configured HTTPS PUBLIC_ORIGIN.")
    configured_host = urlsplit(settings.public_origin).netloc.lower()
    application = FastAPI(
        title="Vibicle",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        redirect_slashes=False,
    )
    application.state.auth = AuthService(engine if engine is not None else make_engine(settings))

    @application.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = str(uuid4())
        response: Response
        try:
            if production and (
                request.scope.get("scheme") != "https"
                or request.headers.getlist("host") != [configured_host]
            ):
                response = error_response(
                    request,
                    403,
                    ErrorData(code="SOURCE_NOT_ALLOWED", message="請使用網站的 HTTPS 網址。"),
                )
            elif request.url.path.startswith("/api/") and "idempotency-key" in request.headers:
                response = error_response(
                    request,
                    400,
                    ErrorData(
                        code="IDEMPOTENCY_NOT_SUPPORTED",
                        message="此介面不接受去重識別碼。",
                    ),
                )
            elif (
                request.url.path.startswith("/api/")
                and "/images/" not in request.url.path
                and ("if-match" in request.headers or "if-unmodified-since" in request.headers)
            ):
                response = error_response(
                    request,
                    400,
                    ErrorData(
                        code="UNSUPPORTED_PRECONDITION",
                        message="請使用規定的資料版本欄位。",
                    ),
                )
            else:
                response = await call_next(request)
        except Exception as exc:
            logging.getLogger("uvicorn.error").error(
                "request_id=%s error_type=%s", request.state.request_id, type(exc).__name__
            )
            response = error_response(
                request,
                500,
                ErrorData(
                    code="INTERNAL_ERROR",
                    outcome="unknown",
                    message="服務發生錯誤，請以 Request ID 查詢。",
                ),
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        logging.getLogger("uvicorn.error").info(
            "request_id=%s status=%s", request.state.request_id, response.status_code
        )
        return response

    @application.exception_handler(ContractError)
    async def handle_contract_error(request: Request, error: ContractError) -> JSONResponse:
        response = error_response(request, error.status, error.error)
        if error.retry_after is not None:
            response.headers["Retry-After"] = str(error.retry_after)
        return response

    @application.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        original = getattr(error, "orig", None)
        if getattr(original, "sqlstate", None) in {"55P03", "40P01", "40001"}:
            return error_response(
                request,
                503,
                ErrorData(code="CONCURRENCY_BUSY", message="資料忙碌，請重新讀取。"),
            )
        return error_response(
            request,
            503,
            ErrorData(code="STORE_UNAVAILABLE", message="資料服務暫時無法使用。"),
        )

    @application.exception_handler(HTTPException)
    async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
        response = error_response(
            request,
            error.status_code,
            ErrorData(
                code="METHOD_NOT_ALLOWED" if error.status_code == 405 else "RESOURCE_NOT_FOUND",
                message="此路徑或方法不可用。",
            ),
        )
        if error.headers and "Allow" in error.headers:
            response.headers["Allow"] = error.headers["Allow"]
        return response

    application.include_router(auth_router)
    application.include_router(vehicle_router)
    application.include_router(history_router)
    application.include_router(image_router)
    return application


app = create_app()
