"""Consistent error responses and global exception handlers.

Every error the API emits shares one envelope::

    {"error": {"code": "<machine_code>", "message": "<human text>",
               "details": <optional structured data>}}

so clients can branch on ``error.code`` and always render ``error.message``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("taskify")

# HTTP status -> stable machine-readable error code.
_STATUS_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    422: "validation_error",  # literal avoids the ENTITY/CONTENT deprecation churn
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_502_BAD_GATEWAY: "bad_gateway",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


def error_response(
    status_code: int,
    message: str,
    *,
    code: str | None = None,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a ``JSONResponse`` carrying the standard error envelope."""

    body: dict[str, Any] = {
        "error": {
            "code": code or _STATUS_CODES.get(status_code, "error"),
            "message": message,
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render ``HTTPException`` (and Starlette's) in the standard envelope."""

    detail = exc.detail
    if isinstance(detail, str):
        message, details = detail, None
    else:
        # FastAPI allows structured detail; preserve it under ``details``.
        message, details = "Request failed.", detail
    return error_response(
        exc.status_code,
        message,
        details=details,
        headers=getattr(exc, "headers", None),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render request-body/query validation failures with field-level detail."""

    details = [
        {
            # Drop the leading "body"/"query" location element for readability.
            "field": ".".join(str(part) for part in err.get("loc", [])[1:]) or "(request)",
            "message": err.get("msg", "Invalid value."),
            "type": err.get("type", "value_error"),
        }
        for err in exc.errors()
    ]
    return error_response(
        422,
        "Request validation failed.",
        details=details,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so an unexpected error never leaks a stack trace to the client."""

    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An unexpected error occurred.",
        code="internal_error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the standard exception handlers on the app."""

    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
