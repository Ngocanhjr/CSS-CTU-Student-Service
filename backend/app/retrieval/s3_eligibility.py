# định nghĩa tài liệu nào được phép đưa vào tìm kiếm retrieval (dense+sparse)
# Cần kiểm tra: Tên field trong Qdrant payload phải đúng với dữ liệu upsert thực tế.
# Retrieval chỉ đọc phiên bản mới nhất đã được duyệt và publish.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import models as qmodels

from app.databases.models import Document, DocumentVersion


@dataclass(frozen=True)
class EligibilityContext:
    audience: str = "sinh_vien"
    document_key: str | None = None
    version_key: str | None = None


class EligibilityPolicy:
    @staticmethod
    def build_postgres_conditions(
        context: EligibilityContext,
    ) -> list[Any]:
        conditions: list[Any] = [
            DocumentVersion.review_status == "approved",
            DocumentVersion.rag_status == "published",
            DocumentVersion.is_latest.is_(True),
        ]

        if context.audience:
            conditions.append(Document.audience.contains([context.audience]))

        if context.document_key:
            conditions.append(
                Document.document_key == context.document_key
            )

        if context.version_key:
            conditions.append(
                DocumentVersion.version_key == context.version_key
            )

        return conditions

    @staticmethod
    def build_qdrant_filter(
        context: EligibilityContext,
        *,
        chunk_type: str = "child",
    ) -> qmodels.Filter:
        must: list[qmodels.FieldCondition] = [
            qmodels.FieldCondition(
                key="review_status",
                match=qmodels.MatchValue(value="approved"),
            ),
            qmodels.FieldCondition(
                key="rag_status",
                match=qmodels.MatchValue(value="published"),
            ),
            qmodels.FieldCondition(
                key="is_latest",
                match=qmodels.MatchValue(value=True),
            ),
            qmodels.FieldCondition(
                key="chunk_type",
                match=qmodels.MatchValue(value=chunk_type),
            ),
        ]

        if context.audience:
            must.append(
                qmodels.FieldCondition(
                    key="audience",
                    match=qmodels.MatchValue(value=context.audience),
                )
            )

        if context.document_key:
            must.append(
                qmodels.FieldCondition(
                    key="document_key",
                    match=qmodels.MatchValue(
                        value=context.document_key
                    ),
                )
            )

        if context.version_key:
            must.append(
                qmodels.FieldCondition(
                    key="version_key",
                    match=qmodels.MatchValue(
                        value=context.version_key
                    ),
                )
            )

        return qmodels.Filter(must=must)
