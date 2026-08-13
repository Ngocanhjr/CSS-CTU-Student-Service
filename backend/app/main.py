from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging_setup import setup_logging
from app.api.admin_ingestion import router as admin_ingestion_router
from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.api.reference import router as reference_router
from app.api.router import api_router


setup_logging()


class UTF8JSONResponse(JSONResponse):
    """Trả JSON kèm charset=utf-8 để client (PowerShell, curl) giải mã đúng tiếng Việt."""

    media_type = "application/json; charset=utf-8"


app = FastAPI(
    title="CTU Student Service API",
    version="0.1.0",
    default_response_class=UTF8JSONResponse,
)

# CORS: cho phép Flutter web (chạy ở localhost/127.0.0.1 với port ngẫu nhiên)
# gọi API. Native (Android emulator/điện thoại) không đi qua CORS nên không bị ảnh hưởng.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router)

app.include_router(
    admin_ingestion_router,
    prefix="/api/v1",
)
app.include_router(
    documents_router,
    prefix="/api/v1",
)
app.include_router(
    reference_router,
    prefix="/api/v1",
)
