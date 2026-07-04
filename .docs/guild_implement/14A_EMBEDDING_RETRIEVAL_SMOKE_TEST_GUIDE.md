# 14A. Huong Dan Smoke Test Embedding + Retrieval Khong Qua DB

**Last Updated:** 2026-06-25

File nay la guide rieng de test nhanh:

```text
markdown_reader -> chunker -> embedding -> Qdrant -> retrieval
```

Khong thay the guide 11/12/13/14/15 chinh thuc.

---

## 1. Muc Tieu

Muc tieu cua smoke test:

```text
- Kiem tra chunker tao child chunks co search duoc khong.
- Kiem tra embedding model chay duoc.
- Kiem tra Qdrant upsert/search duoc.
- Test nhanh retrieval truoc khi implement PostgreSQL repository va pipeline chinh thuc.
```

Khong lam trong guide nay:

```text
- Khong ghi PostgreSQL.
- Khong tao DocumentChunk.id.
- Khong map parent_chunk_key -> parent_chunk_id.
- Khong tao ingestion job.
- Khong xu ly publish status.
- Khong thay the pipeline production.
```

---

## 2. File Can Tao/Sua

14A van la smoke test, nhung function nen dat vao dung module ngay tu dau de sau nay 14/15/16 chi can hoan thien tiep.

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/app/ingestion/smoke_embedding_retrieval.py
```

`smoke_embedding_retrieval.py` chi orchestration test local. Khong dat logic embedding/vectorstore chinh trong file smoke.

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

## 4. Flow Tong The

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

Chi embed child chunks trong smoke test:

```python
child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]
```

Parent chunks chua can embed trong smoke test. Parent se dung sau de mo rong context/repository.

---

## 5. Payload Qdrant Toi Thieu

Moi point trong Qdrant can co payload:

```python
{
    "document_key": chunk.document_key,
    "version_key": chunk.version_key,
    "title": document.metadata.title,
    "department": document.metadata.department,
    "document_type": document.metadata.document_type,
    "domain": document.metadata.domain,
    "chunk_key": chunk.chunk_key,
    "parent_chunk_key": chunk.parent_chunk_key,
    "chunk_type": chunk.chunk_type,
    "heading_path": chunk.heading_path,
    "page_start": chunk.page_start,
    "page_end": chunk.page_end,
    "content": chunk.content,
}
```

Luu y:

```text
Khong co db_chunk_id/document_version_id trong smoke test vi bo qua PostgreSQL.
Dung chunk_key lam stable key de debug.
Embedding text co context, nhung payload/content van giu raw chunk.content de hien thi/citation.
Metadata filter trong smoke test se filter tren payload nay, khong filter trong PostgreSQL.
```

---

## 6. Collection Qdrant De Xuat

Dung collection rieng cho smoke test:

```text
ctu_chunks_smoke
```

Khong dung chung collection production de tranh lan data test.

Neu dung BGE-M3, vector size thuong la:

```text
1024
```

Distance:

```text
Cosine
```

---

## 7. Embedding Adapter Tam Thoi

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Trong 14A, `embed_texts()` van la adapter nho, nhung dat ngay trong `app/embedding/embedder.py` de sau nay guide 14 hoan thien tiep, khong phai di chuyen file.

Yeu cau:

```text
- Input: list[str]
- Output: list vector cung thu tu voi input
- Moi vector co cung dimension voi Qdrant collection
```

Implementation that cua `embed_texts()` nam o muc 8, dung LangChain `NVIDIAEmbeddings`. Khong de `pass`, `...`, hoac `NotImplementedError` khi bat dau chay smoke test.

Guide 14 se hoan thien them `TextEmbedder` protocol va `LangChainNvidiaEmbedder` trong cung file nay.

---

## 8. Dung NVIDIA API Key Qua LangChain

Da chot RAG pipeline di theo LangChain, nen smoke test 14A cung dung LangChain embedding de khong lech voi production.

Ly do:

```text
Chunker da dung langchain-text-splitters.
Embedding/retrieval dung LangChain giup thong nhat interface.
14A smoke test se gan voi 14/15 production hon, it phai refactor lai.
```

NVIDIA NIM retrieval API co endpoint embedding:

```text
https://integrate.api.nvidia.com/v1/embeddings
```

Vi du model:

```text
baai/bge-m3
```

NVIDIA docs ghi endpoint nay nhan `model`, `input`, `encoding_format`, `truncate`; `input` co the la string hoac array string va khong duoc rong. Xem NVIDIA API docs: https://docs.api.nvidia.com/nim/reference/baai-bge-m3-invoke

Bien moi truong:

```powershell
$env:NVIDIA_API_KEY="nvapi-..."
```

Hoac trong `.env` local:

```text
NVIDIA_API_KEY=nvapi-...
NVIDIA_EMBEDDING_MODEL=baai/bge-m3
```

Khong commit `.env` hoac API key.

### Dependency

Them vao `requirements.txt`:

```text
langchain-nvidia-ai-endpoints
```

Neu sau nay dung Qdrant integration cua LangChain, them:

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

Luu y:

```text
Huong chinh la LangChain NVIDIAEmbeddings.
Neu package doi signature, sua theo version package dang cai thay vi doi sang client khac trong 14A.
```

---

## 9. Vector Cache De Tiet Kiem Credit

Nen lam cache ngay trong smoke test de tranh goi NVIDIA embedding lai nhieu lan khi chay thu.

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Cache theo:

```text
chunk_key + model_name + text_hash
```

Khong chi cache theo `chunk_key`, vi neu embedding text doi nhung key van giong thi vector cu se sai.

File cache de xuat:

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
from pathlib import Path
from typing import Any


CACHE_PATH = Path(".cache/embedding_vectors.json")


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

Embed voi cache:

```python
def build_smoke_embedding_text(document: MarkdownDocument, chunk: Chunk) -> str:
    metadata = document.metadata
    page = f"Trang: {chunk.page_start}-{chunk.page_end}"
    return "\n".join(
        [
            f"Tai lieu: {metadata.title}",
            f"Don vi: {metadata.department}",
            f"Loai: {metadata.document_type}",
            f"Muc: {' > '.join(chunk.heading_path)}",
            page,
            "",
            chunk.content.strip(),
        ]
    )


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

Luu y:

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
    return "\n".join(
        [
            f"Tai lieu: {metadata.title}",
            f"Don vi: {metadata.department}",
            f"Loai: {metadata.document_type}",
            f"Muc: {' > '.join(chunk.heading_path)}",
            page,
            "",
            chunk.content.strip(),
        ]
    )


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


SMOKE_COLLECTION_NAME = "ctu_chunks_smoke"
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
        department=metadata.department,
        document_type=metadata.document_type,
        domain=metadata.domain,
        chunk_key=chunk.chunk_key,
        parent_chunk_key=chunk.parent_chunk_key,
        chunk_type=chunk.chunk_type,
        heading_path=chunk.heading_path,
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


def search_smoke_points(
    client: QdrantClient,
    *,
    query_vector: list[float],
    collection_name: str = SMOKE_COLLECTION_NAME,
    top_k: int = 5,
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
    chunks = chunk_markdown_document(document)
    child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]
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
    top_k: int = 5,
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

---

## 11. Qdrant Point ID

Smoke test chot dung UUID stable tu `chunk_key`.

```python
import uuid


def point_id_from_chunk_key(chunk_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))
```

Van luu `chunk_key` trong payload de debug, nhung Qdrant point id dung UUID o tren.

---

## 12. Ket Qua Search Can In Ra

Moi result nen in:

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

Dung output nay de xem retrieval co tra dung van ban khong.

Luu y:

```text
search_smoke_points() tra ve list[QdrantSearchResult], khong phai list[dict].
Vi vay consumer phai dung `item.score` va `item.payload`.
Khong dung `item["score"]` hoac `item["payload"]`, neu khong se gap TypeError: 'QdrantSearchResult' object is not subscriptable.
```

---

## 13. Metadata Filter Theo Ngu Canh

Trong 14A, metadata filter la Qdrant payload filter, khong phai PostgreSQL filter.

Filter mac dinh:

```python
RetrievalFilter(chunk_type="child")
```

Ly do: smoke test chi embed child chunks, nen search nen gioi han vao child ngay tu dau.

Filter theo ngu canh nen ho tro:

```text
department
document_type
domain
document_key
version_key
chunk_type
```

Y nghia:

```text
department: gioi han theo don vi/phong ban, vi du CTSV.
document_type: gioi han theo loai tai lieu, vi du quy_trinh, thong_bao, quy_dinh.
domain: gioi han theo mien nghiep vu, vi du student_service.
document_key: test dung mot tai lieu cu the.
version_key: test dung mot version cu the.
chunk_type: mac dinh child; chi doi khi can debug parent sau nay.
```

Khong dua cac filter nay lam mac dinh bat buoc trong 14A:

```text
review_status=approved
rag_status=published
audience_student=true
```

Ly do: neu collection smoke/production da chi nap cac chunk approved + valid + published + audience_student thi cac filter status nay gan nhu khong con gia tri runtime. Co the them sau nhu safety guard, nhung filter chinh nen la ngu canh.

---

## 13A. Optional Demo RAG Chain Sau Khi Retrieval Chay

Sau khi 14A da search ra top-k chunks, co the demo them LangChain pipe:

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

Neu 14A da build san `context_str` tu top-k results, khong truyen thang string vao dict pipe:

```python
# Sai vi context_str la str.
{"context": context_str, "question": RunnablePassthrough()}
```

Dung:

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

Neu khong boc `context_str`, se gap:

```text
TypeError: Expected a Runnable, callable or dict. Instead got an unsupported type: <class 'str'>
```

Nhung day chi la demo hoc LangChain chain, khong phai production flow cua project.

Trong project nay, production khong nen dua raw Qdrant retriever thang vao prompt vi:

```text
Qdrant khong phai source of truth.
Content/citation cuoi cung phai hydrate tu PostgreSQL.
Query mo ho nhu "dieu kien la gi" phai clarification/context completion truoc.
Citation phai validate truoc khi tra cho user.
```

Flow dung sau 14A:

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

Huong dan chi tiet nam o:

```text
chatbot/.docs/guild_implement/18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md
```

14A van uu tien muc tieu:

```text
markdown -> chunk -> embedding -> Qdrant -> retrieval
```

Chua can LLM answer de ket luan smoke test embedding/retrieval thanh cong.

---

## 14. Lenh Chay

Tu backend:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
python -m app.ingestion.smoke_embedding_retrieval
```

Sau khi chay, chuong trinh hoi tung gia tri trong console:

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

Voi pipeline interactive, nen boc prompt trong `while True` de hoi lien tuc:

```text
Question (nhập 0 để dừng):
```

Neu nguoi dung nhap:

```text
0
```

thi dung chuong trinh ngay, khong retrieval va khong goi LLM. Neu nhap cau hoi khac, chuong trinh tra loi xong se quay lai hoi tiep.

Neu khong can filter nao thi de trong va bam Enter.

Vi du debug rieng mot tai lieu/version:

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

Neu loi import `app`, dam bao dang dung folder:

```text
chatbot/backend
```

---

## 15. Checklist Done

- [ ] Doc duoc Markdown bang `read_markdown_document()`.
- [ ] Chunk duoc bang `chunk_markdown_document()`.
- [ ] Co child chunks.
- [ ] Co `NVIDIA_API_KEY` trong environment local.
- [ ] Embedding model tra vector dung dimension.
- [ ] Vector cache theo `chunk_key + model + text_hash`.
- [ ] Chay lai smoke test khong embed lai chunk da cache.
- [ ] Tao duoc Qdrant collection rieng `ctu_chunks_smoke`.
- [ ] Upsert duoc child chunks.
- [ ] Query tra ve top-k results.
- [ ] Result co `chunk_key`, `heading_path`, `page_start/page_end`, `content_preview`.
- [ ] Payload co `title`, `department`, `document_type`, `domain`.
- [ ] Search smoke test truyen duoc `RetrievalFilter`.
- [ ] Filter theo `department`, `document_type`, `domain`, `document_key`, `version_key`, `chunk_type` hoat dong.
- [ ] Khong can PostgreSQL de chay smoke test.

---

## 16. Khi Nao Quay Lai 11/12/13

Sau khi smoke test chung minh retrieval co tin hieu tot, quay lai lam:

```text
11 Chunk Preview
12 PostgreSQL Ingestion Repository
13 Pipeline Orchestration
14 Embedding module chinh thuc
15 Qdrant vectorstore chinh thuc
```

Ly do:

```text
Smoke test chi kiem tra search duoc hay khong.
Production van can PostgreSQL de quan ly version, status, parent_chunk_id, ingestion job, publish workflow.
```
