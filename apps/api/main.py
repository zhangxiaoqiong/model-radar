"""FastAPI application factory.

- RFC 9457 problem+json for all error responses
- X-Request-ID echoed / generated on every request
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .deps import UnauthorizedError
from .routers import admin, public


def _problem(status: int, title: str, detail: str | None = None,
             request_id: str | None = None) -> JSONResponse:
    body: dict = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status, content=body,
                        media_type="application/problem+json")


_STATUS_TITLES = {
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
    422: "Unprocessable Entity", 429: "Too Many Requests",
    500: "Internal Server Error", 503: "Service Unavailable",
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLM Observatory API",
        version="0.1.0",
        description="V1a: model registry, raw evaluations, admin operations",
    )
    app.include_router(public.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError):
        return _problem(401, "Unauthorized", exc.detail,
                        getattr(request.state, "request_id", None))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        title = _STATUS_TITLES.get(exc.status_code, "Error")
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _problem(exc.status_code, title, detail,
                        getattr(request.state, "request_id", None))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return _problem(422, "Unprocessable Entity", str(exc.errors()[:3]),
                        getattr(request.state, "request_id", None))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return _problem(500, "Internal Server Error", None,
                        getattr(request.state, "request_id", None))

    return app


app = create_app()
