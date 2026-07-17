
# question
# → embed_query() từ embedder.py
# → search_points() từ repository.py
# → Qdrant filter chunk_type = child
# → LangChainDocument[] cho hydration.py


"""Dense retrieval of eligible child chunks from Qdrant."""

from langchain_core.documents import Document as LangChainDocument

from app.embedding.embedder import embed_query
from app.vectorstore.models import QdrantSearchResult, RetrievalFilter
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import search_points


DEFAULT_TOP_K = 5


def retrieve_child_chunks(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    document_key: str | None = None,
    version_key: str | None = None,
) -> list[LangChainDocument]:
    """Embed a query and return its matching child chunks from Qdrant."""
    query_vector = embed_query(query)
    points: list[QdrantSearchResult] = search_points(
        get_qdrant_client(),
        query_vector=query_vector,
        top_k=top_k,
        filters=RetrievalFilter(
            document_key=document_key,
            version_key=version_key,
            chunk_type="child",
        ),
    )

    return [
        LangChainDocument(
            page_content=str(point.payload.get("content", "")),
            metadata={
                **point.payload,
                "_score": point.score,
            },
        )
        for point in points
    ]
