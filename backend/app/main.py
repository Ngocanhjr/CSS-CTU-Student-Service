from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_ingestion import router as admin_ingestion_router
from app.api.documents import router as documents_router
from app.api.exception_handlers import register_exception_handlers
from app.api.health import router as health_router
from app.api.ocr import router as ocr_router
from app.api.reference import router as reference_router
from app.api.router import api_router


app = FastAPI(
    title="CTU Student Service API",
    version="0.1.0",
)
register_exception_handlers(app)

# Cho phép frontend local và các deployment Vercel gọi thẳng Render. Upload
# không đi qua Vercel proxy vì proxy giới hạn request body khoảng 4,5 MB.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^(?:https?://(?:localhost|127\.0\.0\.1)(?::\d+)?"
        r"|https://[a-z0-9-]+\.vercel\.app)$"
    ),
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
    ocr_router,
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
