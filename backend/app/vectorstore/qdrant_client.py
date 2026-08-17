# Tạo kết nối đến Qdrant bằng cấu hình môi trường.

import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient


# The project .env is one level above ``backend``.  Uvicorn is normally
# launched from ``backend``, so a plain environment lookup would otherwise
# silently fall back to localhost:6333 instead of the configured Qdrant Cloud
# instance.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key)
