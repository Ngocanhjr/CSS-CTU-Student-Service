# 15. Part H - Huong Dan Implement Qdrant Vectorstore

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan H.

Muc tieu:

```text
Tao Qdrant client
ensure collection
upsert child chunk vectors
search voi filter student
cap nhat DocumentChunk.qdrant_point_id va index_status
```

Neu da lam smoke test theo:

```text
chatbot/.docs/guild_implement/14A_EMBEDDING_RETRIEVAL_SMOKE_TEST_GUIDE.md
```

thi guide nay la buoc chuan hoa production:

```text
14A ensure_collection() -> app/vectorstore/repository.py
14A point_id_from_chunk_key() -> make_point_id(version_key, chunk_key)
14A payload toi thieu -> build_chunk_payload() day du metadata DB/status
14A search top-k -> search_points()
```

Khac biet quan trong:

```text
14A bo qua PostgreSQL.
Guide 15 production nhan chunks da luu DB, co db_chunk_id/document_version_id, va update qdrant_point_id/index_status ve PostgreSQL.
Da chot RAG pipeline di theo LangChain, nen retrieval layer dung LangChain Qdrant retriever.
Repository nay van can de kiem soat payload/status DB ro rang.
```

---

## 1. File Can Tao/Sua

```text
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/test/vectorstore/test_qdrant_repository.py
```

---

## 2. Requirements

File:

```text
chatbot/backend/requirements.txt
```

Them:

```text
qdrant-client>=1.9
langchain-qdrant
```

Test:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "import qdrant_client; print('qdrant client ok')"
```

---

## 3. Qdrant Client

File:

```text
chatbot/backend/app/vectorstore/qdrant_client.py
```

Suggested pattern:

```python
import os

from qdrant_client import QdrantClient


def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key)
```

Neu dung local docker khong auth, `api_key=None` ok.

---

## 4. Models

File:

```text
chatbot/backend/app/vectorstore/models.py
```

Dung dataclass cho input upsert:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class VectorPoint:
    db_chunk_id: int
    db_parent_chunk_id: int | None
    version_key: str
    chunk_key: str
    vector: list[float]
    payload: dict
```

Search result:

```python
@dataclass(frozen=True)
class VectorSearchResult:
    point_id: str
    score: float
    payload: dict
```

---

## 5. Stable Point ID

Vi `Chunk.chunk_key` la stable key va duoc luu vao DB, Qdrant point id tao tu `version_key + chunk_key`:

```python
from uuid import NAMESPACE_URL, uuid5


def make_point_id(version_key: str, chunk_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ctu-student-service/chunk/{version_key}/{chunk_key}"))
```

Ly do:

```text
Cung version_key + chunk_key -> cung Qdrant point id.
Upsert idempotent.
Khong dung random uuid.
Khong dung PostgreSQL id lam dinh danh vector chinh.
```

---

## 6. Ensure Collection

File:

```text
chatbot/backend/app/vectorstore/repository.py
```

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


DEFAULT_COLLECTION = "ctu_student_service_chunks"
VECTOR_NAME = "embedding"


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str = DEFAULT_COLLECTION,
    vector_size: int,
) -> None:
    collections = client.get_collections().collections
    names = {collection.name for collection in collections}

    if collection_name in names:
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            VECTOR_NAME: VectorParams(size=vector_size, distance=Distance.COSINE),
        },
    )
```

Luu y:

```text
vector_size lay tu len(vector dau tien), khong hardcode khi dung fake embedder.
```

---

## 7. Build Payload

Payload can du de filter va trace:

```python
def build_chunk_payload(
    *,
    db_chunk_id: int,
    db_parent_chunk_id: int | None,
    chunk_key: str,
    parent_chunk_key: str | None,
    chunk_type: str,
    document_key: str,
    version_key: str,
    document_type: str,
    domain: str,
    audience: list[str],
    review_status: str,
    rag_status: str,
    is_latest: bool,
    page_start: int | None,
    page_end: int | None,
) -> dict:
    return {
        "chunk_key": chunk_key,
        "parent_chunk_key": parent_chunk_key,
        "postgres_chunk_id": db_chunk_id,
        "postgres_parent_chunk_id": db_parent_chunk_id,
        "chunk_type": chunk_type,
        "document_key": document_key,
        "version_key": version_key,
        "document_type": document_type,
        "domain": domain,
        "audience": audience,
        "audience_student": "student" in audience,
        "review_status": review_status,
        "rag_status": rag_status,
        "is_latest": is_latest,
        "page_start": page_start,
        "page_end": page_end,
    }
```

---

## 8. Upsert Points

```python
from qdrant_client.models import PointStruct


def upsert_points(
    client: QdrantClient,
    *,
    points: list[VectorPoint],
    collection_name: str = DEFAULT_COLLECTION,
) -> list[str]:
    if not points:
        return []

    vector_size = len(points[0].vector)
    ensure_collection(client, collection_name=collection_name, vector_size=vector_size)

    qdrant_points = [
        PointStruct(
            id=make_point_id(point.version_key, point.chunk_key),
            vector={VECTOR_NAME: point.vector},
            payload=point.payload,
        )
        for point in points
    ]

    client.upsert(collection_name=collection_name, points=qdrant_points)
    return [str(point.id) for point in qdrant_points]
```

---

## 9. Metadata Filter Theo Ngu Canh

```python
from dataclasses import dataclass

from qdrant_client.models import FieldCondition, Filter, MatchValue


@dataclass(frozen=True)
class RetrievalFilter:
    document_type: str | None = None
    domain: str | None = None
    document_key: str | None = None
    version_key: str | None = None
    chunk_type: str | None = "child"


def build_context_filter(filters: RetrievalFilter | None = None) -> Filter | None:
    if filters is None:
        filters = RetrievalFilter()

    conditions = []

    if filters.document_type:
        conditions.append(FieldCondition(key="document_type", match=MatchValue(value=filters.document_type)))
    if filters.domain:
        conditions.append(FieldCondition(key="domain", match=MatchValue(value=filters.domain)))
    if filters.document_key:
        conditions.append(FieldCondition(key="document_key", match=MatchValue(value=filters.document_key)))
    if filters.version_key:
        conditions.append(FieldCondition(key="version_key", match=MatchValue(value=filters.version_key)))
    if filters.chunk_type:
        conditions.append(FieldCondition(key="chunk_type", match=MatchValue(value=filters.chunk_type)))

    if not conditions:
        return None

    return Filter(must=conditions)
```

Student collection chi chua chunks da approved + published + audience_student. Status filter la guard rieng, khong phai filter chinh.

---

## 10. Search

```python
def search_points(
    client: QdrantClient,
    *,
    query_vector: list[float],
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = 5,
    student_only: bool = True,
) -> list[VectorSearchResult]:
    query_filter = build_student_filter() if student_only else None

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=VECTOR_NAME,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    return [
        VectorSearchResult(
            point_id=str(result.id),
            score=result.score,
            payload=result.payload or {},
        )
        for result in response.points
    ]
```

---

## 11. Update DB Sau Upsert

Sau khi upsert Qdrant xong, pipeline/repository can update:

```text
DocumentChunk.qdrant_point_id
DocumentChunk.index_status = indexed
DocumentVersion.rag_status = published
```

Suggested helper:

```python
async def mark_chunks_indexed(
    session: AsyncSession,
    *,
    chunk_point_ids: dict[int, str],
) -> None:
    for db_chunk_id, point_id in chunk_point_ids.items():
        chunk = await session.get(DocumentChunk, db_chunk_id)
        if chunk:
            chunk.qdrant_point_id = point_id
            chunk.index_status = "indexed"
```

---

## 12. Test

Unit tests:

```python
from app.vectorstore.repository import build_chunk_payload, make_point_id


def test_make_point_id_is_stable():
    assert make_point_id("doc-v1", "doc-v1::c::0001") == make_point_id(
        "doc-v1", "doc-v1::c::0001"
    )
    assert make_point_id("doc-v1", "doc-v1::c::0001") != make_point_id(
        "doc-v1", "doc-v1::c::0002"
    )


def test_payload_contains_trace_fields():
    payload = build_chunk_payload(
        db_chunk_id=1,
        db_parent_chunk_id=None,
        chunk_key="doc-v1::c::0001",
        parent_chunk_key="doc-v1::p::0001",
        chunk_type="child",
        document_key="doc",
        version_key="doc-v1",
        document_type="quy_trinh",
        domain="dao_tao",
        audience=["student"],
        review_status="approved",
        rag_status="published",
        is_latest=True,
        page_start=1,
        page_end=1,
    )

    assert payload["chunk_key"] == "doc-v1::c::0001"
    assert payload["postgres_chunk_id"] == 1
    assert payload["audience_student"] is True
```

Integration test Qdrant:

```python
@pytest.mark.integration
def test_upsert_and_search_qdrant():
    client = get_qdrant_client()
    vector = [0.1, 0.2, 0.3]
    point = VectorPoint(
        db_chunk_id=1,
        db_parent_chunk_id=None,
        version_key="doc-v1",
        chunk_key="doc-v1::c::0001",
        vector=vector,
        payload={
            "chunk_key": "doc-v1::c::0001",
            "postgres_chunk_id": 1,
            "review_status": "approved",
            "rag_status": "published",
            "audience_student": True,
        },
    )

    upsert_points(client, points=[point], collection_name="test_ctu_chunks")
    results = search_points(
        client,
        query_vector=vector,
        collection_name="test_ctu_chunks",
        top_k=1,
    )

    assert results
```

---

## 13. Lenh Chay Qdrant

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
docker compose up -d qdrant
```

Test:

```powershell
cd backend
..\..\.venv\Scripts\python.exe -m pytest test/vectorstore
```

---

## 14. Done Khi

- [ ] Co Qdrant client factory.
- [ ] Point ID stable theo `version_key + chunk_key`.
- [ ] Ensure collection dung vector size thuc te.
- [ ] Payload co `postgres_chunk_id`, `chunk_key`, `parent_chunk_key`.
- [ ] Student filter co review_status=approved, rag_status=published, audience_student.
- [ ] Upsert va search test duoc.
- [ ] DB update duoc `qdrant_point_id`.

---

## 15. Loi De Gap

### Loi: collection vector size mismatch

Nguyen nhan:

```text
Collection tao bang fake vector 3 dimensions, sau do upsert BGE-M3 1024 dimensions.
```

Xu ly:

```text
Dung collection test rieng cho fake.
Dung collection dev rieng cho BGE-M3.
Neu can, recreate collection.
```

### Loi: duplicate search results

Nguyen nhan:

```text
Point id random.
```

Xu ly:

```text
Dung uuid5 theo `version_key + chunk_key`.
```

### Loi: version chua duyet van search ra

Nguyen nhan:

```text
Filter student thieu review_status/rag_status.
```

Xu ly:

```text
Them hard filter review_status=approved AND rag_status=published trong build_student_filter va test.
```
