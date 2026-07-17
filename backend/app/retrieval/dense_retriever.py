# Mục đích: semantic search bằng LangChain Qdrant retriever.
# Tìm đoạn văn có ý nghĩa gần với câu hỏi, không chỉ tìm từ khóa giống nhau

# - `vector_name=VECTOR_NAME`.
# - Dense side dùng cùng `EligibilityPolicy` với sparse side.
# - Chỉ lấy child chunk cho direct retrieval nếu đó là contract của dự án.



from __future__ import annotations

from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.embedding.embedder import (
    LangChainEmbeddingsAdapter,
    TextEmbedder,
)
from app.retrieval.eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)
from app.vectorstore.repository import (
    DEFAULT_COLLECTION,
    VECTOR_NAME,
)


DEFAULT_TOP_K = 5


def build_dense_retriever(
    *,
    qdrant_client: QdrantClient,
    embedder: TextEmbedder,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    audience: str = "student",
    document_key: str | None = None,
    version_key: str | None = None,
) -> VectorStoreRetriever:
    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=LangChainEmbeddingsAdapter(embedder),
        vector_name=VECTOR_NAME,
    )

    qdrant_filter = EligibilityPolicy.build_qdrant_filter(
        EligibilityContext(
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        ),
        chunk_type="child",
    )

    return vectorstore.as_retriever(
        search_kwargs={
            "k": top_k,
            "filter": qdrant_filter,
        }
    )