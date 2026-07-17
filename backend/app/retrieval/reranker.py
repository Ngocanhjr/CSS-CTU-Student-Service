# Mục đích: cung cấp interface rerank độc lập với vendor.
# Khi tích hợp NVIDIA rerank hoặc cross-encoder, tạo class mới implement cùng interface.

from __future__ import annotations

from typing import Protocol

from app.retrieval.models import RetrievalResult


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    """Chỉ dùng cho test hoặc giai đoạn chưa tích hợp model rerank."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        del query
        return results