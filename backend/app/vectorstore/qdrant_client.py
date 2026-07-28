# Tạo kết nối đến Qdrant bằng cấu hình môi trường.

import os

from qdrant_client import QdrantClient


def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key)