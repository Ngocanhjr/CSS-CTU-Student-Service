# 14A. Hướng Dẫn Smoke Test Embedding + Retrieval Không Qua DB

**Last Updated:** 2026-07-10

> **Trước khi chạy guide này:** chunks phải đi qua pre-chunk structural parsing theo `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md`. Nếu chunker chưa parse đúng heading/item/table/code/page, smoke test ở đây có thể đánh giá sai chất lượng retrieval.

File này là guide riêng để test nhanh:

```text
markdown_reader -> chunker -> embedding -> Qdrant -> retrieval
```

Không thay thế guide 11/12/13/14/15 chính thức.

---

## 1. Mục Tiêu

Mục tiêu của smoke test:

```text
- Kiem tra chunker tao child chunks co search duoc khong.
- Kiem tra embedding model chay duoc.
- Kiem tra Qdrant upsert/search duoc.
- Test nhanh retrieval truoc khi implement PostgreSQL repository va pipeline chinh thuc.
```

Không làm trong guide này:

```text
- Khong ghi PostgreSQL.
- Khong tao DocumentChunk.id.
- Khong map parent_chunk_key -> parent_chunk_id.
- Khong tao ingestion job.
- Khong xu ly publish status.
- Khong thay the pipeline production.
```

---

## 2. File Cần Tạo/Sửa

14A vẫn là smoke test, nhưng function nên đặt vào đúng module ngay từ đầu để sau này 14/15/16 chỉ cần hoàn thiện tiếp.

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/app/ingestion/smoke_embedding_retrieval.py
```

`smoke_embedding_retrieval.py` chỉ orchestration test local. Không đặt logic embedding/vectorstore chính trong file smoke.

---

## 3. Function/File Layout

```text
chatbot/backend/app/embedding/embedder.py
- EMBEDDING_MODEL_NAME
- get_nvidia_embeddings()
- embed_texts()
- embed_query()
- build_smoke_embedding_text()
- hash_text()
- load_vector_cache()
- save_vector_cache()
- embed_chunks_with_cache()
- LangChainNvidiaEmbedder

chatbot/backend/app/vectorstore/qdrant_client.py
- get_qdrant_client()

chatbot/backend/app/vectorstore/models.py
- RetrievalFilter
- QdrantChunkPayload
- QdrantSearchResult

chatbot/backend/app/vectorstore/repository.py
- ensure_collection()
- point_id_from_chunk_key()
- build_context_filter()
- build_smoke_payload()
- upsert_smoke_points()
- search_smoke_points()

chatbot/backend/app/ingestion/smoke_embedding_retrieval.py
- upsert_child_chunks()
- search()
- main()

chatbot/backend/app/ingestion/pipeline.py
- goi repository + embedding + vectorstore sau guide 11/12/13
```

Rule:

```text
14A tao module dung vi tri ngay tu dau.
Guide 14 se hoan thien app/embedding/embedder.py.
Guide 15 se hoan thien app/vectorstore/repository.py.
Guide 16 se hoan thien retrieval tren cac module nay.
smoke_embedding_retrieval.py khong tro thanh pipeline chinh thuc.
```

---

## 4. Flow Tổng Thể

```text
Markdown file
  -> read_markdown_document()
  -> chunk_markdown_document()
  -> loc child chunks
  -> build enriched embedding text tu metadata + heading_path + child content
  -> embed enriched text
  -> upsert Qdrant
  -> embed query
  -> search Qdrant
  -> in top-k ket qua
```

Chỉ embed child chunks trong smoke test:

```python
child_chunks = chunk_result.child_chunks
```

Parent chunks chưa cần embed trong smoke test. Parent sẽ dùng sau để mở rộng context/repository.

---

## 5. Payload Qdrant Tối Thiểu

Mỗi point trong Qdrant cần có payload:

```python
{
    "document_key": chunk.document_key,
    "version_key": chunk.version_key,
    "title": document.metadata.title,
    "department": (document.metadata.responsible_department or ["UNKNOWN"])[0],
    "document_type": document.metadata.document_type,
    "domain": document.metadata.domain,
    "chunk_key": chunk.chunk_key,
    "parent_chunk_key": chunk.parent_chunk_key,
    "chunk_type": chunk.chunk_type,
    "heading_path": chunk.heading_path,
    "item_path": (chunk.metadata or {}).get("item_path", []),
    "logical_item_key": (chunk.metadata or {}).get("logical_item_key"),
    "logical_item_keys": (chunk.metadata or {}).get("logical_item_keys", []),
    "parent_item_key": (chunk.metadata or {}).get("parent_item_key"),
    "split_index": (chunk.metadata or {}).get("split_index", 0),
    "split_count": (chunk.metadata or {}).get("split_count", 1),
    "chunk_index": chunk.chunk_index,
    "item_marker": (chunk.metadata or {}).get("item_marker"),
    "item_level": (chunk.metadata or {}).get("item_level"),
    "page_start": chunk.page_start,
    "page_end": chunk.page_end,
    "content": chunk.content,
}
```

Lưu ý:

```text
Khong co db_chunk_id/document_version_id trong smoke test vi bo qua PostgreSQL.
Dung chunk_key lam stable key de debug.
Embedding text co context, nhung payload/content van giu raw chunk.content de hien thi/citation.
Metadata filter trong smoke test se filter tren payload nay, khong filter trong PostgreSQL.
```

---

## 6. Collection Qdrant Đề Xuất

Dùng collection riêng cho smoke test:

```text
css_qdrant
```

Không dùng chung collection production để tránh lẫn data test.

Nếu dùng BGE-M3, vector size thường là:

```text
1024
```

Distance:

```text
Cosine
```

---

## 7. Embedding Adapter Tạm Thời

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Trong 14A, `embed_texts()` vẫn là adapter nhỏ, nhưng đặt ngay trong `app/embedding/embedder.py` để sau này guide 14 hoàn thiện tiếp, không phải di chuyển file.

Yêu cầu:

```text
- Input: list[str]
- Output: list vector cung thu tu voi input
- Moi vector co cung dimension voi Qdrant collection
```

Implementation thật của `embed_texts()` nằm ở mục 8, dùng LangChain `NVIDIAEmbeddings`. Không để `pass`, `...`, hoặc `NotImplementedError` khi bắt đầu chạy smoke test.

Guide 14 sẽ hoàn thiện thêm `TextEmbedder` protocol và `LangChainNvidiaEmbedder` trong cùng file này.

---

## 8. Dùng NVIDIA API Key Qua LangChain

Đã chốt RAG pipeline đi theo LangChain, nên smoke test 14A cũng dùng LangChain embedding để không lệch với production.

Lý do:

```text
Chunker da dung langchain-text-splitters.
Embedding/retrieval dung LangChain giup thong nhat interface.
14A smoke test se gan voi 14/15 production hon, it phai refactor lai.
```

NVIDIA NIM retrieval API có endpoint embedding:

```text
https://integrate.api.nvidia.com/v1/embeddings
```

Ví dụ model:

```text
baai/bge-m3
```

NVIDIA docs ghi endpoint này nhận `model`, `input`, `encoding_format`, `truncate`; `input` có thể là string hoặc array string và không được rỗng. Xem NVIDIA API docs: https://docs.api.nvidia.com/nim/reference/baai-bge-m3-invoke

Biến môi trường:

```powershell
$env:NVIDIA_API_KEY="nvapi-..."
```

Hoặc trong `.env` local:

```text
NVIDIA_API_KEY=nvapi-...
NVIDIA_EMBEDDING_MODEL=baai/bge-m3
```

Không commit `.env` hoặc API key.

### Dependency

Thêm vào `requirements.txt`:

```text
langchain-nvidia-ai-endpoints
```

Nếu sau này dùng Qdrant integration của LangChain, thêm:

```text
langchain-qdrant
```

### Implementation LangChain

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Import:

```python
import os

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings


EMBEDDING_MODEL_NAME = os.getenv("NVIDIA_EMBEDDING_MODEL", "baai/bge-m3")


def get_nvidia_embeddings() -> NVIDIAEmbeddings:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing NVIDIA_API_KEY")

    return NVIDIAEmbeddings(
        model=EMBEDDING_MODEL_NAME,
        api_key=api_key,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    embeddings = get_nvidia_embeddings()
    return embeddings.embed_documents(texts)
```

Query embedding:

```python
def embed_query(query: str) -> list[float]:
    embeddings = get_nvidia_embeddings()
    return embeddings.embed_query(query)
```

Lưu ý:

```text
Huong chinh la LangChain NVIDIAEmbeddings.
Neu package doi signature, sua theo version package dang cai thay vi doi sang client khac trong 14A.
```

---

## 9. Vector Cache Để Tiết Kiệm Credit

Nên làm cache ngay trong smoke test để tránh gọi NVIDIA embedding lại nhiều lần khi chạy thử.

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Cache theo:

```text
chunk_key + model_name + text_hash
```

Không chỉ cache theo `chunk_key`, vì nếu embedding text đổi nhưng key vẫn giống thì vector cũ sẽ sai.

File cache đề xuất:

```text
chatbot/backend/.cache/embedding_vectors.json
```

Format:

```json
{
  "doc-v1::c::0001": {
    "model": "nvidia/embedding-model-name",
    "text_hash": "sha256...",
    "vector": [0.01, 0.02, 0.03]
  }
}
```

Helpers:

```python
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CACHE_PATH = Path(".cache/embedding_vectors.json")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_vector_cache(path: Path = CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_vector_cache(cache: dict[str, dict[str, Any]], path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
```

Embed với cache:

```python
def build_smoke_embedding_text(document: MarkdownDocument, chunk: Chunk) -> str:
    metadata = document.metadata
    page = f"Trang: {chunk.page_start}-{chunk.page_end}"
    department = ", ".join(metadata.responsible_department or ["UNKNOWN"])
    chunk_metadata = chunk.metadata or {}
    item_path = chunk_metadata.get("item_path", [])
    legal_unit_type = chunk_metadata.get("legal_unit_type", "none")
    content = remove_html_comments(chunk.content).strip()
    lines = [
        f"Tai lieu: {metadata.title}",
        f"Don vi: {department}",
        f"Loai: {metadata.document_type}",
        f"Muc: {' > '.join(chunk.heading_path)}",
    ]
    if legal_unit_type and legal_unit_type != "none":
        lines.append(f"Don vi phap ly: {legal_unit_type}")
    ancestor_item_path = item_path[:-1]
    if ancestor_item_path:
        lines.append(f"Ngu canh muc cha: {' > '.join(ancestor_item_path)}")
    lines.extend([page, "", content])
    return "\n".join(lines)


def remove_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def embed_chunks_with_cache(
    document: MarkdownDocument,
    chunks: list[Chunk],
    *,
    model_name: str,
) -> list[list[float]]:
    cache = load_vector_cache()
    vectors_by_key: dict[str, list[float]] = {}
    missing_chunks: list[Chunk] = []

    for chunk in chunks:
        embedding_text = build_smoke_embedding_text(document, chunk)
        text_hash = hash_text(embedding_text)
        cached = cache.get(chunk.chunk_key)
        if (
            cached
            and cached.get("model") == model_name
            and cached.get("text_hash") == text_hash
        ):
            vectors_by_key[chunk.chunk_key] = cached["vector"]
        else:
            missing_chunks.append(chunk)

    if missing_chunks:
        embedding_texts = [
            build_smoke_embedding_text(document, chunk)
            for chunk in missing_chunks
        ]
        new_vectors = embed_texts(embedding_texts)
        for chunk, vector in zip(missing_chunks, new_vectors, strict=True):
            embedding_text = build_smoke_embedding_text(document, chunk)
            cache[chunk.chunk_key] = {
                "model": model_name,
                "text_hash": hash_text(embedding_text),
                "vector": vector,
            }
            vectors_by_key[chunk.chunk_key] = vector
        save_vector_cache(cache)

    return [vectors_by_key[chunk.chunk_key] for chunk in chunks]
```

Lưu ý:

```text
Cache chi dung cho smoke test local.
Production sau nay nen luu trang thai embedding trong PostgreSQL/Qdrant, khong phu thuoc file cache local.
```

---

## 10. Skeleton Theo File

### 10.1 `app/embedding/embedder.py`

```text
chatbot/backend/app/embedding/embedder.py
```

```python
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk


CACHE_PATH = Path(".cache/embedding_vectors.json")
EMBEDDING_MODEL_NAME = os.getenv("NVIDIA_EMBEDDING_MODEL", "baai/bge-m3")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_vector_cache(path: Path = CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_vector_cache(cache: dict[str, dict[str, Any]], path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def get_nvidia_embeddings() -> NVIDIAEmbeddings:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing NVIDIA_API_KEY")

    return NVIDIAEmbeddings(
        model=EMBEDDING_MODEL_NAME,
        api_key=api_key,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    embeddings = get_nvidia_embeddings()
    return embeddings.embed_documents(texts)


def build_smoke_embedding_text(document: MarkdownDocument, chunk: Chunk) -> str:
    metadata = document.metadata
    page = f"Trang: {chunk.page_start}-{chunk.page_end}"
    department = ", ".join(metadata.responsible_department or ["UNKNOWN"])
    chunk_metadata = chunk.metadata or {}
    item_path = chunk_metadata.get("item_path", [])
    legal_unit_type = chunk_metadata.get("legal_unit_type", "none")
    content = remove_html_comments(chunk.content).strip()
    lines = [
        f"Tai lieu: {metadata.title}",
        f"Don vi: {department}",
        f"Loai: {metadata.document_type}",
        f"Muc: {' > '.join(chunk.heading_path)}",
    ]
    if legal_unit_type and legal_unit_type != "none":
        lines.append(f"Don vi phap ly: {legal_unit_type}")
    ancestor_item_path = item_path[:-1]
    if ancestor_item_path:
        lines.append(f"Ngu canh muc cha: {' > '.join(ancestor_item_path)}")
    lines.extend([page, "", content])
    return "\n".join(lines)


def remove_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def embed_chunks_with_cache(
    document: MarkdownDocument,
    chunks: list[Chunk],
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> list[list[float]]:
    cache = load_vector_cache()
    vectors_by_key: dict[str, list[float]] = {}
    missing_chunks: list[Chunk] = []

    for chunk in chunks:
        embedding_text = build_smoke_embedding_text(document, chunk)
        text_hash = hash_text(embedding_text)
        cached = cache.get(chunk.chunk_key)
        if (
            cached
            and cached.get("model") == model_name
            and cached.get("text_hash") == text_hash
        ):
            vectors_by_key[chunk.chunk_key] = cached["vector"]
        else:
            missing_chunks.append(chunk)

    if missing_chunks:
        embedding_texts = [
            build_smoke_embedding_text(document, chunk)
            for chunk in missing_chunks
        ]
        new_vectors = embed_texts(embedding_texts)
        for chunk, vector in zip(missing_chunks, new_vectors, strict=True):
            embedding_text = build_smoke_embedding_text(document, chunk)
            cache[chunk.chunk_key] = {
                "model": model_name,
                "text_hash": hash_text(embedding_text),
                "vector": vector,
            }
            vectors_by_key[chunk.chunk_key] = vector
        save_vector_cache(cache)

    return [vectors_by_key[chunk.chunk_key] for chunk in chunks]
```

### 10.2 `app/vectorstore/qdrant_client.py`

```text
chatbot/backend/app/vectorstore/qdrant_client.py
```

```python
import os

from qdrant_client import QdrantClient


def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key)
```

### 10.3 `app/vectorstore/models.py`

```text
chatbot/backend/app/vectorstore/models.py
```

```python
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class RetrievalFilter:
    department: str | None = None
    document_type: str | None = None
    domain: str | None = None
    document_key: str | None = None
    version_key: str | None = None
    chunk_type: str | None = "child"


class QdrantChunkPayload(BaseModel):
    document_key: str
    version_key: str
    title: str
    department: str
    document_type: str
    domain: str
    chunk_key: str
    parent_chunk_key: str | None
    chunk_type: str
    heading_path: list[str]
    item_path: list[str] = []
    logical_item_key: str | None = None
    logical_item_keys: list[str] = []
    parent_item_key: str | None = None
    split_index: int = 0
    split_count: int = 1
    chunk_index: int | None = None
    item_marker: str | None = None
    item_level: int | None = None
    page_start: int
    page_end: int
    content: str


@dataclass(frozen=True)
class QdrantSearchResult:
    score: float
    payload: dict
```

Rule:

```text
models.py chi chua shape du lieu vectorstore: filter, payload, search result.
Khong goi Qdrant client trong models.py.
Khong import repository vao models.py.
```

### 10.4 `app/vectorstore/repository.py`

```text
chatbot/backend/app/vectorstore/repository.py
```

```python
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


SMOKE_COLLECTION_NAME = "css_qdrant"
VECTOR_NAME = "embedding"


def point_id_from_chunk_key(chunk_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str = SMOKE_COLLECTION_NAME,
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


def build_context_filter(filters: RetrievalFilter | None = None) -> Filter | None:
    if filters is None:
        filters = RetrievalFilter()

    conditions = []

    if filters.department:
        conditions.append(
            FieldCondition(
                key="department",
                match=MatchValue(value=filters.department),
            )
        )
    if filters.document_type:
        conditions.append(
            FieldCondition(
                key="document_type",
                match=MatchValue(value=filters.document_type),
            )
        )
    if filters.domain:
        conditions.append(
            FieldCondition(
                key="domain",
                match=MatchValue(value=filters.domain),
            )
        )
    if filters.document_key:
        conditions.append(
            FieldCondition(
                key="document_key",
                match=MatchValue(value=filters.document_key),
            )
        )
    if filters.version_key:
        conditions.append(
            FieldCondition(
                key="version_key",
                match=MatchValue(value=filters.version_key),
            )
        )
    if filters.chunk_type:
        conditions.append(
            FieldCondition(
                key="chunk_type",
                match=MatchValue(value=filters.chunk_type),
            )
        )

    if not conditions:
        return None

    return Filter(must=conditions)


def build_smoke_payload(document: MarkdownDocument, chunk: Chunk) -> dict:
    metadata = document.metadata
    payload = QdrantChunkPayload(
        document_key=chunk.document_key,
        version_key=chunk.version_key,
        title=metadata.title,
        department=(metadata.responsible_department or ["UNKNOWN"])[0],
        document_type=metadata.document_type,
        domain=metadata.domain,
        chunk_key=chunk.chunk_key,
        parent_chunk_key=chunk.parent_chunk_key,
        chunk_type=chunk.chunk_type,
        heading_path=chunk.heading_path,
        item_path=(chunk.metadata or {}).get("item_path", []),
        logical_item_key=(chunk.metadata or {}).get("logical_item_key"),
        logical_item_keys=(chunk.metadata or {}).get("logical_item_keys", []),
        parent_item_key=(chunk.metadata or {}).get("parent_item_key"),
        split_index=(chunk.metadata or {}).get("split_index", 0),
        split_count=(chunk.metadata or {}).get("split_count", 1),
        chunk_index=chunk.chunk_index,
        item_marker=(chunk.metadata or {}).get("item_marker"),
        item_level=(chunk.metadata or {}).get("item_level"),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        content=chunk.content,
    )
    return payload.model_dump()


def upsert_smoke_points(
    client: QdrantClient,
    *,
    document: MarkdownDocument,
    chunks: list[Chunk],
    vectors: list[list[float]],
    collection_name: str = SMOKE_COLLECTION_NAME,
) -> int:
    if not chunks:
        return 0

    ensure_collection(
        client,
        collection_name=collection_name,
        vector_size=len(vectors[0]),
    )

    points = [
        PointStruct(
            id=point_id_from_chunk_key(chunk.chunk_key),
            vector={VECTOR_NAME: vector},
            payload=build_smoke_payload(document, chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


DEFAULT_TOP_K = 5


def search_smoke_points(
    client: QdrantClient,
    *,
    query_vector: list[float],
    collection_name: str = SMOKE_COLLECTION_NAME,
    top_k: int = DEFAULT_TOP_K,
    filters: RetrievalFilter | None = None,
) -> list[QdrantSearchResult]:
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=VECTOR_NAME,
        query_filter=build_context_filter(filters),
        limit=top_k,
        with_payload=True,
    )
    return [
        QdrantSearchResult(
            score=result.score,
            payload=result.payload or {},
        )
        for result in response.points
    ]
```

Smoke test có thể giữ default `top_k=5`, nhưng app code chính phải lấy default từ runtime settings. Không dùng `settings.retrieval.top_k or 5`.

### 10.5 `app/ingestion/smoke_embedding_retrieval.py`

```text
chatbot/backend/app/ingestion/smoke_embedding_retrieval.py
```

```python
from __future__ import annotations

from pathlib import Path

from app.embedding.embedder import embed_chunks_with_cache, get_nvidia_embeddings
from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import (
    RetrievalFilter,
    SMOKE_COLLECTION_NAME,
    search_smoke_points,
    upsert_smoke_points,
)


def upsert_child_chunks(path: str | Path) -> int:
    document = read_markdown_document(path)
    chunk_result = chunk_markdown_document(document)
    child_chunks = chunk_result.child_chunks
    if not child_chunks:
        raise ValueError("No child chunks generated")

    vectors = embed_chunks_with_cache(document, child_chunks)
    client = get_qdrant_client()
    return upsert_smoke_points(
        client,
        document=document,
        chunks=child_chunks,
        vectors=vectors,
    )


def search(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    filters: RetrievalFilter | None = None,
) -> list[dict]:
    embeddings = get_nvidia_embeddings()
    query_vector = embeddings.embed_query(query)
    client = get_qdrant_client()
    results = search_smoke_points(
        client,
        query_vector=query_vector,
        top_k=top_k,
        filters=filters,
    )

    return [
        {
            "score": item.score,
            "chunk_key": item.payload.get("chunk_key"),
            "parent_chunk_key": item.payload.get("parent_chunk_key"),
            "heading_path": item.payload.get("heading_path"),
            "page_start": item.payload.get("page_start"),
            "page_end": item.payload.get("page_end"),
            "content_preview": (item.payload.get("content") or "")[:300],
        }
        for item in results
    ]


def main() -> None:
    import json

    path = input("Markdown path: ").strip()
    query = input("Query: ").strip()
   

    if not path:
        raise ValueError("Markdown path is required")
    if not query:
        raise ValueError("Query is required")

    top_k = 5

    inserted = upsert_child_chunks(path)
    filters = RetrievalFilter(
        department=department,
        document_type=document_type,
        domain=domain,
        document_key=document_key,
        version_key=version_key,
        chunk_type=chunk_type,
    )
    results = search(query, top_k=top_k, filters=filters)

    print(
        json.dumps(
            {
                "collection": SMOKE_COLLECTION_NAME,
                "inserted_child_chunks": inserted,
                "query": query,
                "filters": filters.__dict__,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
```

Nếu smoke script đọc settings, dùng default trong settings model. Không fallback bằng `or`.

---

## 11. Qdrant Point ID

Smoke test chốt dùng UUID stable từ `chunk_key`.

```python
import uuid


def point_id_from_chunk_key(chunk_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))
```

Vẫn lưu `chunk_key` trong payload để debug, nhưng Qdrant point id dùng UUID ở trên.

---

## 12. Kết Quả Search Cần In Ra

Mỗi result nên in:

```python
{
    "score": item.score,
    "chunk_key": item.payload["chunk_key"],
    "parent_chunk_key": item.payload["parent_chunk_key"],
    "heading_path": item.payload["heading_path"],
    "page_start": item.payload["page_start"],
    "page_end": item.payload["page_end"],
    "content_preview": item.payload["content"][:300],
}
```

Dùng output này để xem retrieval có trả đúng văn bản không.

Lưu ý:

```text
search_smoke_points() tra ve list[QdrantSearchResult], khong phai list[dict].
Vi vay consumer phai dung `item.score` va `item.payload`.
Khong dung `item["score"]` hoac `item["payload"]`, neu khong se gap TypeError: 'QdrantSearchResult' object is not subscriptable.
```

---

## 13. Metadata Filter Theo Ngữ Cảnh

Trong 14A, metadata filter là Qdrant payload filter, không phải PostgreSQL filter.

Filter mặc định:

```python
RetrievalFilter(chunk_type="child")
```

Lý do: smoke test chỉ embed child chunks, nên search nên giới hạn vào child ngay từ đầu.

Filter theo ngữ cảnh nên hỗ trợ:

```text
department
document_type
domain
document_key
version_key
chunk_type
```

Ý nghĩa:

```text
department: gioi han theo don vi/phong ban, vi du CTSV.
document_type: gioi han theo loai tai lieu, vi du quy_trinh, thong_bao, quy_dinh.
domain: gioi han theo mien nghiep vu, vi du student_service.
document_key: test dung mot tai lieu cu the.
version_key: test dung mot version cu the.
chunk_type: mac dinh child; chi doi khi can debug parent sau nay.
```

Không đưa các filter này làm mặc định bắt buộc trong 14A:

```text
review_status=approved
rag_status=published
audience_student=true
```

Lý do: nếu collection smoke/production đã chỉ nạp các chunk approved + valid + published + audience_student thì các filter status này gần như không còn giá trị runtime. Có thể thêm sau như safety guard, nhưng filter chính nên là ngữ cảnh.

---

## 13A. Optional Demo RAG Chain Sau Khi Retrieval Chạy

Sau khi 14A đã search ra top-k chunks, có thể demo thêm LangChain pipe:

```python
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

question = input("Question: ")
answer = rag_chain.invoke(question)
```

Nếu 14A đã build sẵn `context_str` từ top-k results, không truyền thẳng string vào dict pipe:

```python
# Sai vi context_str la str.
{"context": context_str, "question": RunnablePassthrough()}
```

Dùng:

```python
from langchain_core.runnables import RunnableLambda, RunnablePassthrough


rag_chain = (
    {
        "context": RunnableLambda(lambda _: context_str),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)
```

Nếu không bọc `context_str`, sẽ gặp:

```text
TypeError: Expected a Runnable, callable or dict. Instead got an unsupported type: <class 'str'>
```

Nhưng đây chỉ là demo học LangChain chain, không phải production flow của project.

Trong project này, production không nên đưa raw Qdrant retriever thẳng vào prompt vì:

```text
Qdrant khong phai source of truth.
Content/citation cuoi cung phai hydrate tu PostgreSQL.
Query mo ho nhu "dieu kien la gi" phai clarification/context completion truoc.
Citation phai validate truoc khi tra cho user.
```

Flow đúng sau 14A:

```text
question
  -> query clarification/context completion
  -> retrieval top-k
  -> hydrate PostgreSQL
  -> build cited context
  -> prompt
  -> llm
  -> parse answer
  -> validate citations
```

Hướng dẫn chi tiết nằm ở:

```text
chatbot/.docs/guild_implement/18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md
```

14A vẫn ưu tiên mục tiêu:

```text
markdown -> chunk -> embedding -> Qdrant -> retrieval
```

Chưa cần LLM answer để kết luận smoke test embedding/retrieval thành công.

---

## 14. Lệnh Chạy

Từ backend:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
python -m app.ingestion.smoke_embedding_retrieval
```

Sau khi chạy, chương trình hỏi từng giá trị trong console:

```text
Markdown path: app/ingestion/chunking/test/02_1470KHTH_06-05-2024.md
Query: kế hoạch này có nhiệm vụ gì
Top K [5]: 5
Department filter (optional): ctsv
Document type filter (optional): ke_hoach
Domain filter (optional):
Document key filter (optional): ctu-ctsv-02-1470khth-06-05-2024
Version key filter (optional): ctu-ctsv-02-1470khth-06-05-2024-7aa5eda77e08
Chunk type [child]: child
```

Với pipeline interactive, nên bọc prompt trong `while True` để hỏi liên tục:

```text
Question (nhập 0 để dừng):
```

Nếu người dùng nhập:

```text
0
```

thì dừng chương trình ngay, không retrieval và không gọi LLM. Nếu nhập câu hỏi khác, chương trình trả lời xong sẽ quay lại hỏi tiếp.

Nếu không cần filter nào thì để trống và bấm Enter.

Ví dụ debug riêng một tài liệu/version:

```text
Markdown path: path/to/document.md
Query: điều kiện là gì
Top K [5]:
Department filter (optional):
Document type filter (optional):
Domain filter (optional):
Document key filter (optional): xin-giay-khai-sinh
Version key filter (optional): xin-giay-khai-sinh-v1
Chunk type [child]:
```

Nếu lỗi import `app`, đảm bảo đang dùng folder:

```text
chatbot/backend
```

---

## 15. Checklist Done

- [ ] Đọc được Markdown bằng `read_markdown_document()`.
- [ ] Chunk được bằng `chunk_markdown_document()`.
- [ ] Có child chunks.
- [ ] Có `NVIDIA_API_KEY` trong environment local.
- [ ] Embedding model trả vector đúng dimension.
- [ ] Vector cache theo `chunk_key + model + text_hash`.
- [ ] Chạy lại smoke test không embed lại chunk đã cache.
- [ ] Tạo được Qdrant collection riêng `css_qdrant`.
- [ ] Upsert được child chunks.
- [ ] Query trả về top-k results.
- [ ] Result có `chunk_key`, `heading_path`, `page_start/page_end`, `content_preview`.
- [ ] Payload có `title`, `department`, `document_type`, `domain`.
- [ ] Search smoke test truyền được `RetrievalFilter`.
- [ ] Filter theo `department`, `document_type`, `domain`, `document_key`, `version_key`, `chunk_type` hoạt động.
- [ ] Không cần PostgreSQL để chạy smoke test.

---

## 16. Khi Nào Quay Lại 11/12/13

Sau khi smoke test chứng minh retrieval có tín hiệu tốt, quay lại làm:

```text
11 Chunk Preview
12 PostgreSQL Ingestion Repository
13 Pipeline Orchestration
14 Embedding module chinh thuc
15 Qdrant vectorstore chinh thuc
```

Lý do:

```text
Smoke test chi kiem tra search duoc hay khong.
Production van can PostgreSQL de quan ly version, status, parent_chunk_id, ingestion job, publish workflow.
```
