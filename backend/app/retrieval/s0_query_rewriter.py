"""Generate safe semantic search variants for a student question."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.llm.generator import get_chat_model

logger = logging.getLogger(__name__)

DEFAULT_MAX_QUERIES = 3
DEFAULT_TIMEOUT_SECONDS = 12.0


def _max_queries() -> int:
    value = os.getenv("QUERY_REWRITE_MAX_QUERIES", str(DEFAULT_MAX_QUERIES))
    try:
        return max(1, min(int(value), 5))
    except ValueError:
        return DEFAULT_MAX_QUERIES


def _is_enabled() -> bool:
    return os.getenv("QUERY_REWRITE_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def get_query_rewrite_timeout_seconds() -> float:
    value = os.getenv(
        "QUERY_REWRITE_TIMEOUT_SECONDS",
        str(DEFAULT_TIMEOUT_SECONDS),
    )
    try:
        return max(1.0, min(float(value), 30.0))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _response_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    return str(content)


def _parse_variants(question: str, content: str, max_queries: int) -> list[str]:
    """Accept only a small JSON payload and always retain the original query."""

    candidates: list[Any] = []
    try:
        decoded = json.loads(content)
        if isinstance(decoded, dict):
            candidates = decoded.get("queries", [])
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                decoded = json.loads(content[start : end + 1])
                if isinstance(decoded, dict):
                    candidates = decoded.get("queries", [])
            except json.JSONDecodeError:
                pass

    variants = [question]
    seen = {question.casefold().strip()}
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        normalized = " ".join(candidate.split()).strip()
        key = normalized.casefold()
        if not normalized or len(normalized) > 2_000 or key in seen:
            continue
        variants.append(normalized)
        seen.add(key)
        if len(variants) >= max_queries:
            break

    return variants


def rewrite_query(question: str, *, model: Any | None = None) -> list[str]:
    """Return the original question plus up to two retrieval-focused variants.

    A failed rewrite must never block search: the caller receives the original
    question unchanged.
    """

    normalized_question = " ".join(question.split()).strip()
    if not normalized_question or not _is_enabled():
        return [normalized_question] if normalized_question else []

    prompt = f"""
Bạn chuẩn hóa truy vấn tìm kiếm cho chatbot hỗ trợ sinh viên CTU.

Hãy trả về DUY NHẤT JSON theo dạng:
{{"queries":["..."]}}

Quy tắc:
- Tạo tối đa {_max_queries() - 1} biến thể, ngoài câu hỏi gốc.
- Diễn đạt lại theo thuật ngữ quy định/hành chính khi điều đó giúp tìm tài liệu
  có cùng ý nghĩa.
- Giữ nguyên ý định, chủ thể và điều kiện của câu hỏi; không trả lời câu hỏi.
- Không bịa tên văn bản, điều luật, ngày tháng, số liệu hoặc thông tin mới.
- Nếu không có cách viết lại hữu ích, trả về mảng rỗng.

Câu hỏi gốc: {normalized_question}
""".strip()

    try:
        response = (
            model
            or get_chat_model(
                max_tokens=256,
                timeout_seconds=get_query_rewrite_timeout_seconds(),
            )
        ).invoke(prompt)
        return _parse_variants(
            normalized_question,
            _response_content(response),
            _max_queries(),
        )
    except Exception as exc:
        logger.warning("Query rewrite failed; using the original query: %s", exc)
        return [normalized_question]
