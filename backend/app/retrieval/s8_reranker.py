from __future__ import annotations

from dataclasses import replace
import logging
import os
import re
from typing import Protocol

import httpx
from dotenv import find_dotenv, load_dotenv

from app.retrieval.models import RetrievalResult


logger = logging.getLogger(__name__)


# Đọc biến môi trường từ file .env của dự án.
load_dotenv(find_dotenv())


class Reranker(Protocol):
    """Quy ước chung cho các lớp reranker."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    """Không xếp hạng lại; chủ yếu dùng trong unit test."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        del query
        return results


class LexicalReranker:
    """Xếp hạng lại bằng từ khóa, không phụ thuộc dịch vụ ngoài.

    Ưu tiên mức độ phủ từ khóa của câu hỏi trong nội dung chunk, cộng thêm
    điểm nhỏ cho khớp ở tiêu đề và cho cụm câu hỏi xuất hiện nguyên vẹn.
    Giữ nguyên thứ tự gốc khi các chunk bằng điểm.

    Dùng làm fallback khi Jina Reranker không khả dụng.
    """

    # Các từ ít mang nghĩa tìm kiếm -> bỏ qua để tính điểm chính xác hơn.
    _STOP_WORDS = frozenset(
        {
            "a",
            "an",
            "and",
            "cho",
            "của",
            "các",
            "cần",
            "có",
            "để",
            "gì",
            "khi",
            "là",
            "một",
            "nào",
            "những",
            "ở",
            "the",
            "thì",
            "và",
            "về",
            "với",
        }
    )

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        """Chuẩn hóa text thành tập từ khóa: chữ thường, bỏ từ ngắn và stop words."""
        return {
            token
            for token in re.findall(r"\w+", text.casefold())
            if len(token) > 1 and token not in cls._STOP_WORDS
        }

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        query_tokens = self._tokens(query)
        if not query_tokens or len(results) < 2:
            return results

        normalized_query = " ".join(query.casefold().split())
        reranked: list[tuple[float, int, RetrievalResult]] = []

        for position, result in enumerate(results):
            content_tokens = self._tokens(result.content)
            title_tokens = self._tokens(result.title)

            content_overlap = len(query_tokens & content_tokens)
            title_overlap = len(query_tokens & title_tokens)

            # Độ phủ từ khóa trong nội dung.
            coverage = content_overlap / len(query_tokens)
            # Mật độ từ khóa: chunk ngắn mà nhiều từ khớp thì điểm cao hơn.
            density = content_overlap / max(len(content_tokens), 1)
            # Khớp ở tiêu đề.
            title_coverage = title_overlap / len(query_tokens)

            normalized_content = " ".join(result.content.casefold().split())
            phrase_bonus = 0.2 if normalized_query in normalized_content else 0.0

            relevance_score = (
                coverage
                + (0.25 * density)
                + (0.3 * title_coverage)
                + phrase_bonus
            )

            reranked.append(
                (
                    relevance_score,
                    position,
                    replace(result, score=relevance_score),
                )
            )

        reranked.sort(key=lambda item: (-item[0], item[1]))
        return [result for _, _, result in reranked]


class JinaReranker:
    """Xếp hạng lại kết quả retrieval bằng Jina Reranker API.

    Jina nhận câu hỏi và danh sách tài liệu, sau đó trả về thứ tự
    tài liệu theo mức độ liên quan.

    Toàn bộ dữ liệu của RetrievalResult được giữ nguyên.
    Chỉ trường score được thay bằng relevance_score của Jina.
    """

    DEFAULT_ENDPOINT = "https://api.jina.ai/v1/rerank"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jina-reranker-v3",
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 120.0,
    ) -> None:
        api_key = api_key.strip()
        model = model.strip()
        endpoint = endpoint.strip().rstrip("/")

        if not api_key:
            raise ValueError(
                "Jina API key không được để trống."
            )

        if not model:
            raise ValueError(
                "Tên model Jina không được để trống."
            )

        if not endpoint:
            raise ValueError(
                "Jina endpoint không được để trống."
            )

        if timeout <= 0:
            raise ValueError(
                "JINA_RERANK_TIMEOUT phải lớn hơn 0."
            )

        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    @staticmethod
    def _build_document(
        result: RetrievalResult,
    ) -> str:
        """Ghép tiêu đề và nội dung thành document gửi cho Jina."""

        title = (result.title or "").strip()
        content = (result.content or "").strip()

        if not title and not content:
            raise ValueError(
                "RetrievalResult phải có title hoặc content."
            )

        if title and content:
            return (
                f"Tiêu đề: {title}\n"
                f"Nội dung: {content}"
            )

        return title or content

    def _rank(
        self,
        query: str,
        documents: list[str],
    ) -> list[tuple[int, float]]:
        """Gọi Jina API và trả về danh sách (index, score)."""

        request_body = {
            "model": self.model,
            "query": query,
            "documents": documents,

            # Yêu cầu Jina trả về toàn bộ documents đã xếp hạng.
            "top_n": len(documents),

            # Không cần trả lại nội dung vì ứng dụng ánh xạ bằng index.
            "return_documents": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                trust_env=False,
                http2=False,
            ) as client:
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json=request_body,
                )

                response.raise_for_status()
                payload = response.json()

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Jina Reranker trả HTTP "
                f"{exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Jina Reranker phản hồi quá thời gian."
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Không kết nối được Jina Reranker: {exc}"
            ) from exc

        except ValueError as exc:
            raise RuntimeError(
                "Jina Reranker trả response "
                "không phải JSON hợp lệ."
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Jina Reranker trả response "
                "không đúng định dạng object."
            )

        entries = payload.get("results")

        if not isinstance(entries, list):
            raise RuntimeError(
                "Response Jina không có trường "
                "'results' hợp lệ."
            )

        if len(entries) != len(documents):
            raise RuntimeError(
                "Số kết quả Jina trả về không khớp "
                "số documents đầu vào. "
                f"Đầu vào: {len(documents)}, "
                f"đầu ra: {len(entries)}."
            )

        rankings: list[tuple[int, float]] = []
        seen_indexes: set[int] = set()

        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeError(
                    "Một phần tử trong Jina results "
                    "không đúng định dạng object."
                )

            index = entry.get("index")
            relevance_score = entry.get(
                "relevance_score"
            )

            if (
                not isinstance(index, int)
                or isinstance(index, bool)
            ):
                raise RuntimeError(
                    "Jina result thiếu index hợp lệ."
                )

            if index < 0 or index >= len(documents):
                raise RuntimeError(
                    f"Jina trả index ngoài phạm vi: {index}."
                )

            if index in seen_indexes:
                raise RuntimeError(
                    f"Jina trả index trùng lặp: {index}."
                )

            if (
                not isinstance(
                    relevance_score,
                    (int, float),
                )
                or isinstance(relevance_score, bool)
            ):
                raise RuntimeError(
                    f"Jina result tại index {index} "
                    "thiếu relevance_score hợp lệ."
                )

            seen_indexes.add(index)

            rankings.append(
                (
                    index,
                    float(relevance_score),
                )
            )

        # Bảo đảm kết quả được sắp xếp theo điểm giảm dần.
        # Nếu bằng điểm thì giữ ưu tiên theo index ban đầu.
        rankings.sort(
            key=lambda item: (
                -item[1],
                item[0],
            )
        )

        return rankings

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Xếp hạng lại danh sách RetrievalResult."""

        normalized_query = query.strip()

        if not normalized_query:
            return results

        if len(results) < 2:
            return results

        documents = [
            self._build_document(result)
            for result in results
        ]

        rankings = self._rank(
            query=normalized_query,
            documents=documents,
        )

        return [
            replace(
                results[index],
                score=relevance_score,
            )
            for index, relevance_score in rankings
        ]


class FallbackReranker:
    """Ưu tiên reranker chính, tự lùi về reranker dự phòng khi nó lỗi.

    Reranker chính gọi API bên ngoài nên có thể timeout hoặc mất kết nối.
    Khi đó xếp hạng vẫn phải chạy được: thà xếp hạng kém chính xác hơn
    một chút còn hơn để cả request RAG thất bại.
    """

    def __init__(
        self,
        *,
        primary: Reranker,
        fallback: Reranker,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        try:
            return self.primary.rerank(query, results)
        except (RuntimeError, ValueError) as exc:
            logger.warning(
                "Reranker chính thất bại (%s), dùng %s thay thế.",
                exc,
                type(self.fallback).__name__,
            )
            return self.fallback.rerank(query, results)


def get_reranker() -> Reranker:
    """Khởi tạo reranker từ biến môi trường.

    Trả về JinaReranker được bọc bởi :class:`FallbackReranker` để lùi về
    :class:`LexicalReranker` khi Jina lỗi. Nếu chưa cấu hình JINA_API_KEY
    thì dùng luôn LexicalReranker, giúp môi trường dev/test không bắt buộc
    phải có API key.
    """

    api_key = os.getenv(
        "JINA_API_KEY",
        "",
    ).strip()

    if not api_key:
        logger.warning(
            "Chưa cấu hình JINA_API_KEY, dùng LexicalReranker."
        )
        return LexicalReranker()

    model = os.getenv(
        "JINA_RERANK_MODEL",
        "jina-reranker-v3",
    ).strip()

    endpoint = os.getenv(
        "JINA_RERANK_URL",
        JinaReranker.DEFAULT_ENDPOINT,
    ).strip()

    # 8s: đủ cho Jina trả lời ở điều kiện mạng bình thường (~1s), nhưng
    # không giữ cả request RAG lại quá lâu khi mạng tới api.jina.ai chậm.
    timeout_text = os.getenv(
        "JINA_RERANK_TIMEOUT",
        "8",
    ).strip()

    try:
        timeout = float(timeout_text)
    except ValueError as exc:
        raise ValueError(
            "JINA_RERANK_TIMEOUT phải là một số."
        ) from exc

    return FallbackReranker(
        primary=JinaReranker(
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            timeout=timeout,
        ),
        fallback=LexicalReranker(),
    )