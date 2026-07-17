# Mục đích: hợp nhất dense và sparse bằng Reciprocal Rank Fusion.
# RRF không so sánh trực tiếp dense score và sparse score vì hai score có thang đo khác nhau. Nó kết hợp dựa trên thứ hạng.



from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument


def reciprocal_rank_fusion(
    dense_docs: list[LangChainDocument],
    sparse_docs: list[LangChainDocument],
    *,
    limit: int,
    rank_constant: int = 60,
) -> list[LangChainDocument]:
    docs_by_key: dict[str, LangChainDocument] = {}
    fusion_scores: dict[str, float] = {}

    for ranked_docs in (dense_docs, sparse_docs):
        for rank, doc in enumerate(ranked_docs, start=1):
            chunk_key = doc.metadata.get("chunk_key")
            if not chunk_key:
                continue

            key = str(chunk_key)
            docs_by_key.setdefault(key, doc)
            fusion_scores[key] = (
                fusion_scores.get(key, 0.0)
                + 1.0 / (rank_constant + rank)
            )

    ordered_keys = sorted(
        fusion_scores,
        key=fusion_scores.get,
        reverse=True,
    )[:limit]

    return [
        LangChainDocument(
            page_content=docs_by_key[key].page_content,
            metadata={
                **docs_by_key[key].metadata,
                "_score": fusion_scores[key],
            },
        )
        for key in ordered_keys
    ]