from __future__ import annotations

from dataclasses import replace
import json
import os
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.retrieval.models import RetrievalResult

#Là interface/quy ước chung: mọi reranker phải có hàm rerank(query, results) và trả về danh sách
class Reranker(Protocol):
    """Rank hydrated candidates by their relevance to a user query."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        ...

#Không xếp hạng lại, trả nguyên kết quả. Dùng cho test hoặc khi không có model reranker.
class IdentityReranker:
    """Leave candidates unchanged; useful for tests and controlled fallbacks."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        del query
        return results

#Xếp hạng lại theo từ khóa. Nó so sánh các từ quan trọng trong câu hỏi với content và title của chunk.
class LexicalReranker:
    """Dependency-free reranker for the MVP before a cross-encoder is added.

    It prioritizes query-term coverage in the chunk, then applies small boosts
    for matches in the title and for an exact normalized query phrase.  The
    original order is retained when candidates receive the same score.
    """
    #các từ ít mang nghĩa tìm kiếm -> bỏ qua để tính điểm chính xác hơn
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

    #Chuẩn hóa text thành tập từ khóa: chuyển chữ thường, tách từ, bỏ từ ngắn và stop words.#
    @classmethod
    def _tokens(cls, text: str) -> set[str]:
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

        #chuẩn hóa câu hỏi thành tập từ khóa quan trọng
        normalized_query = " ".join(query.casefold().split())
        reranked: list[tuple[float, int, RetrievalResult]] = []

        #duyệt từng chunk để tính điểm liên quan
        for position, result in enumerate(results):
            #Chuẩn hóa content và title của chunk thành tập từ khóa
            content_tokens = self._tokens(result.content)
            title_tokens = self._tokens(result.title)
            
            #đếm số từ khóa của câu hỏi trong content và title
            content_overlap = len(query_tokens & content_tokens)
            title_overlap = len(query_tokens & title_tokens)
            
            #mật độ từ khóa trong chunk, 
            coverage = content_overlap / len(query_tokens)
            
            #tỷ lệ từ khóa trong content, nhiều từ -> điểm cao
            density = content_overlap / max(len(content_tokens), 1)
            
            #tỷ lệ từ khóa trong title
            title_coverage = title_overlap / len(query_tokens)
            normalized_content = " ".join(result.content.casefold().split())
            
            #nếu câu hỏi xuất hiện nguyên cụm trong content thì cộng 0.2
            phrase_bonus = 0.2 if normalized_query in normalized_content else 0.0
            
            #độ phủ từ khóa trong content
            relevance_score = (
                coverage
                + (0.25 * density)
                + (0.3 * title_coverage)
                + phrase_bonus
            )

            reranked.append(
                (
                    #Giữ nguyên toàn bộ dữ liệu của chunk, chỉ thay score bằng điểm rerank mới.
                    relevance_score,
                    position,
                    replace(result, score=relevance_score),
                )
            )
        #sắp xếp chunk theo điểm từ cao xuống thấp
        reranked.sort(key=lambda item: (-item[0], item[1]))
        return [result for _, _, result in reranked]


#Xếp hạng lại bằng cross-encoder chạy trên Text Embeddings Inference (BAAI/bge-reranker-v2-m3).
#Gọi endpoint /rerank của container TEI thứ 2, model chấm trực tiếp cặp (query, chunk).
class CrossEncoderReranker:
    """HTTP client tối thiểu cho reranker cross-encoder chạy trên TEI.

    TEI expose endpoint ``/rerank`` nhận ``{"query", "texts"}`` và trả về danh
    sách ``{"index", "score"}`` đã sắp xếp giảm dần theo độ liên quan.  Ta ánh xạ
    score đó ngược lại từng ``RetrievalResult`` và giữ nguyên toàn bộ metadata.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _score(self, query: str, texts: list[str]) -> list[float]:
        request = Request(
            f"{self.base_url}/rerank",
            data=json.dumps(
                {"query": query, "texts": texts}
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"TEI reranker trả HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Không kết nối được TEI reranker: {exc.reason}"
            ) from exc

        #TEI trả list[{"index", "score"}] đã sắp xếp; ta khôi phục theo index gốc.
        if not isinstance(payload, list) or len(payload) != len(texts):
            raise RuntimeError(
                "TEI reranker trả response không đúng contract."
            )

        scores = [0.0] * len(texts)
        for entry in payload:
            index = entry["index"]
            scores[index] = float(entry["score"])
        return scores

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        if not query.strip() or len(results) < 2:
            return results

        scores = self._score(query, [result.content for result in results])

        reranked: list[tuple[float, int, RetrievalResult]] = [
            (
                score,
                position,
                replace(result, score=score),
            )
            for position, (result, score) in enumerate(zip(results, scores))
        ]
        #điểm cao xuống thấp; giữ thứ tự gốc khi bằng điểm
        reranked.sort(key=lambda item: (-item[0], item[1]))
        return [result for _, _, result in reranked]


def get_reranker() -> Reranker:
    """Tạo reranker cross-encoder từ cấu hình môi trường.

    Fallback về :class:`LexicalReranker` khi TEI reranker chưa được cấu hình,
    giúp môi trường dev/test không bắt buộc phải chạy container thứ 2.
    """
    base_url = os.getenv("TEI_RERANKER_BASE_URL")
    api_key = os.getenv("TEI_RERANKER_API_KEY")

    if not base_url or not api_key:
        return LexicalReranker()

    return CrossEncoderReranker(base_url=base_url, api_key=api_key)
