# Fusion gộp các chunk từ dense và sparse retrieval.
# Chunk xuất hiện hoặc xếp hạng cao ở cả hai nhánh sẽ có RRF score cao hơn.
# Kết quả là danh sách chunk đã hợp nhất, loại bỏ chunk trùng lặp.
# RRF không so sánh trực tiếp dense score và sparse score vì hai score có thang đo khác nhau. Nó kết hợp dựa trên thứ hạng.

from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument


def reciprocal_rank_fusion(
    #lấy danh sách chunk từ dense và sparse
    dense_docs: list[LangChainDocument],
    sparse_docs: list[LangChainDocument],
    *,
    
    limit: int,
    rank_constant: int = 60, #theo gợi ý của paper
) -> list[LangChainDocument]:
    
    #lưu chunk theo chunk_key, để loại bỏ chunk trùng 
    docs_by_key: dict[str, LangChainDocument] = {}
    
    #lưu điểm RRF tổng của từng chunk
    fusion_scores: dict[str, float] = {}
    for ranked_docs in (dense_docs, sparse_docs):
        for rank, doc in enumerate(ranked_docs, start=1):
            #duyệt từng chunk và lấy thứ hạng bắt đầu từ 1
            chunk_key = doc.metadata.get("chunk_key")
            #nếu không có chunk_key thì bỏ qua
            if not chunk_key:
                continue
            #nếu chưa có chunk_key lưu lại, đến khi chunk xuất hiện ở nhánh còn lại thì giữ doc của chunk trước đó, không tạo bản sao
            key = str(chunk_key)
            docs_by_key.setdefault(key, doc)
            
            #Cộng điểm RRF theo công thức 
            fusion_scores[key] = (
                fusion_scores.get(key, 0.0)
                + 1.0 / (rank_constant + rank)
            )
    #sắp chunk_key theo điểm RRF giảm dần 
    ordered_keys = sorted(
        fusion_scores,
        key=fusion_scores.get,
        reverse=True,
    )[:limit]

    #trả về kq ds LangChainDocument gồm các chunk đã được gộp, loại trùng và chọn theo thứ hạng tốt nhất.
    #
    return [
        LangChainDocument(
            page_content=docs_by_key[key].page_content,
            metadata={
                **docs_by_key[key].metadata,
                "_score": fusion_scores[key],  #điểm RRF mới tính từ thứ hạng của dense và sparse
            },
        )
        for key in ordered_keys
    ]