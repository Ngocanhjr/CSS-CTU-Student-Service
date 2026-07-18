from __future__ import annotations

from dataclasses import replace
import os
import re
from typing import Protocol

from langchain_core.documents import Document as LangChainDocument
from langchain_nvidia_ai_endpoints import NVIDIARerank

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


class NVIDIAReranker:
    """Rerank hydrated chunks with NVIDIA NeMo Retriever Reranking NIM.

    The hosted endpoint reads ``NVIDIA_API_KEY`` automatically. Set
    ``NVIDIA_RERANK_BASE_URL`` when the reranking NIM is self-hosted.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        truncate: str = "END",
    ) -> None:
        self.model = model or os.getenv(
            "NVIDIA_RERANK_MODEL",
            "nvidia/llama-nemotron-rerank-1b-v2",
        )
        self.api_key = api_key
        self.base_url = base_url or os.getenv("NVIDIA_RERANK_BASE_URL")
        self.truncate = truncate

    def _build_client(self, *, top_n: int) -> NVIDIARerank:
        options: dict[str, object] = {
            "model": self.model,
            "top_n": top_n,
            "truncate": self.truncate,
        }
        if self.api_key:
            options["api_key"] = self.api_key
        if self.base_url:
            options["base_url"] = self.base_url

        return NVIDIARerank(**options)

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        if not query.strip() or len(results) < 2:
            return results
        if len(results) > 512:
            raise ValueError("NVIDIA reranking supports at most 512 candidates")

        candidates = [
            LangChainDocument(
                page_content=result.content,
                metadata={"_retrieval_result_index": index},
            )
            for index, result in enumerate(results)
        ]
        reranked_documents = self._build_client(
            top_n=len(candidates)
        ).compress_documents(
            documents=candidates,
            query=query,
        )

        reranked_results: list[RetrievalResult] = []
        selected_indexes: set[int] = set()
        for document in reranked_documents:
            index = document.metadata.get("_retrieval_result_index")
            if not isinstance(index, int) or index in selected_indexes:
                continue

            selected_indexes.add(index)
            relevance_score = document.metadata.get("relevance_score")
            score = (
                float(relevance_score)
                if relevance_score is not None
                else results[index].score
            )
            reranked_results.append(replace(results[index], score=score))

        # Keep a complete result set even if a provider returns fewer candidates.
        reranked_results.extend(
            result
            for index, result in enumerate(results)
            if index not in selected_indexes
        )
        return reranked_results
