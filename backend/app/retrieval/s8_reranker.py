from __future__ import annotations

from dataclasses import replace
import os
from typing import Protocol

import httpx
from dotenv import find_dotenv, load_dotenv

from app.retrieval.models import RetrievalResult


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


def get_reranker() -> Reranker:
    """Khởi tạo JinaReranker từ biến môi trường."""

    api_key = os.getenv(
        "JINA_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "Chưa cấu hình JINA_API_KEY "
            "trong file .env."
        )

    model = os.getenv(
        "JINA_RERANK_MODEL",
        "jina-reranker-v3",
    ).strip()

    endpoint = os.getenv(
        "JINA_RERANK_URL",
        JinaReranker.DEFAULT_ENDPOINT,
    ).strip()

    timeout_text = os.getenv(
        "JINA_RERANK_TIMEOUT",
        "120",
    ).strip()

    try:
        timeout = float(timeout_text)
    except ValueError as exc:
        raise ValueError(
            "JINA_RERANK_TIMEOUT phải là một số."
        ) from exc

    return JinaReranker(
        api_key=api_key,
        model=model,
        endpoint=endpoint,
        timeout=timeout,
    )