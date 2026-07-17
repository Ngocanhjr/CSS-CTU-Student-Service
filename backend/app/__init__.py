from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.admin_ingestion import router as admin_ingestion_router

app = FastAPI(title="CTU Student Service API")

app.include_router(health_router)
app.include_router(admin_ingestion_router)