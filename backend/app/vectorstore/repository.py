import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk
from app.vectorstore.models import (
    QdrantChunkPayload,
    QdrantSearchResult,
    RetrievalFilter,
)
