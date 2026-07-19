
# Câu hỏi
# → S2 tách metadata
# → S3 tạo điều kiện eligibility
# → embed câu hỏi thành vector
# → Qdrant tìm các child chunk tương đồng -> đánh giá điểm tương đồng ngữ nghĩa
# → trả về LangChainDocument: danh sách chunk từ Qdrant/vector search


"""Dense retrieval of eligible child chunks from Qdrant."""

from langchain_core.documents import Document as LangChainDocument
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    IsEmptyCondition,
    IsNullCondition,
    PayloadField,
)

from app.embedding.embedder import embed_query
from app.retrieval.s2_metadata_filter import (
    QueryMetadataFilter,
    extract_metadata_filter,
)
from app.retrieval.s3_eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)
from app.vectorstore.models import QdrantSearchResult, RetrievalFilter
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import (
    COLLECTION_NAME,
    build_context_filter,
    search_points,
)


DEFAULT_TOP_K = 5 #số chunk cần lấy, mặc định 5

# embed câu hỏi thành vector
def retrieve_child_chunks(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    audience: str = "sinh_vien",
    document_key: str | None = None,
    version_key: str | None = None,
    metadata_filter: QueryMetadataFilter | None = None, #lấy kết quả đã tách từ metadata_filter
    qdrant_client: QdrantClient | None = None,
    collection_name: str = COLLECTION_NAME,
) -> list[LangChainDocument]:
    """Embed a query and return its matching child chunks from Qdrant."""
    metadata_filter = metadata_filter or extract_metadata_filter(
        query,
        document_key=document_key,
        version_key=version_key,
    )
    #s3 sinh filter, đảm bảo chỉ lấy các chunk theo điều kiện 
    eligibility_filter = EligibilityPolicy.build_qdrant_filter(
        EligibilityContext(
            audience=audience,
            document_key=metadata_filter.document_key,
            version_key=metadata_filter.version_key,
        ),
        #là child chunk
        chunk_type="child",
    )
    
    #Tạo metadata_filter từ s2
    metadata_qdrant_filter = build_context_filter(
        RetrievalFilter(
            department=metadata_filter.department,
            document_type=metadata_filter.document_type,
            domain=metadata_filter.domain,
        )
    )
    #gộp vào s3 -> Qdrant chỉ tìm trong tập dữ liệu vừa hợp lệ vừa đúng ngữ cảnh câu hỏi.
    combined_filter = Filter(
        must=[
            *eligibility_filter.must,
            *(metadata_qdrant_filter.must if metadata_qdrant_filter else []),
        ],
        # Hydration requires a PostgreSQL chunk ID. Exclude old or incomplete
        # Qdrant points that cannot be hydrated into a RetrievalResult.
        must_not=[
            IsNullCondition(
                is_null=PayloadField(key="postgres_chunk_id"),
            ),
            IsEmptyCondition(
                is_empty=PayloadField(key="postgres_chunk_id"),
            ),
        ],
    )
    
    #đổi câu hỏi thành vector
    query_vector = embed_query(query)
    
    #search_points dùng vector đó tìm các vector gần nhất trong Qdrant 
    points: list[QdrantSearchResult] = search_points(
        qdrant_client or get_qdrant_client(),
        query_vector=query_vector,
        collection_name=collection_name,
        top_k=top_k,
        query_filter=combined_filter,
    )

    #KQ Qdrant đổi thành LangChainDocument 
    return [
        LangChainDocument(
            page_content=str(point.payload.get("content", "")),
            metadata={
                #do payload của Qdrant đã gồm các field rồi, nên chỉ cần gọi payload là được
                **point.payload,
                "qdrant_point_id": point.point_id,
                "_score": point.score, #điểm tương đồng giữa 2 vector
            },
        )
        for point in points
        if point.payload.get("postgres_chunk_id") is not None
    ]
