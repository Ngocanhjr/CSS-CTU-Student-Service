from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    ExternalServiceError,
    InvalidRequestError,
    NotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    handlers = {
        NotFoundError: status.HTTP_404_NOT_FOUND,
        InvalidRequestError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ConflictError: status.HTTP_409_CONFLICT,
        ExternalServiceError: status.HTTP_503_SERVICE_UNAVAILABLE,
    }

    for exception_type, status_code in handlers.items():
        app.add_exception_handler(
            exception_type,
            _json_error_handler(status_code),
        )


def _json_error_handler(status_code: int):
    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc)},
        )

    return handle
