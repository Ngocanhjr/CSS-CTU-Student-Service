# 14. Part G - Huong Dan Implement Embedding

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan G.

Muc tieu:

```text
Tao abstraction embedder theo LangChain
format text dau vao cho chunk
co fake embedder de test nhanh
co real NVIDIA/BGE-M3 embedder cho integration
```

MVP chi embed child chunks.

Neu da lam smoke test theo:

```text
chatbot/.docs/guild_implement/14A_EMBEDDING_RETRIEVAL_SMOKE_TEST_GUIDE.md
```

thi guide nay khong phai cai lai tu dau. Chuyen cac phan da test tot sang module chinh thuc:

```text
14A embed_texts() -> app/embedding/embedder.py
14A model choice/vector dimension -> TextEmbedder/LangChainNvidiaEmbedder
14A query embedding -> embed_query()
```

Khac biet quan trong:

```text
14A doc Markdown va chunk truc tiep de smoke test.
Guide 14 production khong doc Markdown, khong chunk.
Guide 14 nhan chunks/DB rows tu pipeline sau guide 12/13.
Da chot RAG pipeline di theo LangChain, nen real embedder production dung LangChain NVIDIA embeddings.
```

---

## 1. File Can Tao/Sua

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/embedding/__init__.py
chatbot/backend/app/embedding/embeder.py
chatbot/backend/test/embedding/test_embedder.py
```

File `embeder.py` dang sai chinh ta. Khong can xoa ngay. Tao `embedder.py`, roi de `embeder.py` re-export.

---

## 2. Requirements

File:

```text
chatbot/backend/requirements.txt
```

Them:

```text
numpy>=1.26
langchain-nvidia-ai-endpoints
```

Unit test dung fake embedder. Integration test can `NVIDIA_API_KEY`.

---

## 3. Data Input Cho Embedding

Khong embed moi raw content. Nen them context:

```text
Tai lieu: <title>
Don vi: <department>
Loai: <document_type>
Muc: <heading_path>
Trang: <page_start>-<page_end>

<content>
```

Function:

```python
def build_embedding_text(
    *,
    title: str,
    department: str,
    document_type: str,
    heading_path: list[str],
    page_start: int | None,
    page_end: int | None,
    content: str,
) -> str:
    page = ""
    if page_start and page_end:
        page = f"Trang: {page_start}-{page_end}"
    elif page_start:
        page = f"Trang: {page_start}"

    lines = [
        f"Tai lieu: {title}".strip(),
        f"Don vi: {department}".strip(),
        f"Loai: {document_type}".strip(),
        f"Muc: {' > '.join(heading_path)}".strip(),
    ]
    if page:
        lines.append(page)

    lines.append("")
    lines.append(content.strip())
    return "\n".join(line for line in lines if line is not None)
```

---

## 4. Embedder Interface

File:

```text
chatbot/backend/app/embedding/embedder.py
```

Suggested pattern:

```python
from typing import Protocol


class TextEmbedder(Protocol):
    model_name: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, query: str) -> list[float]:
        raise NotImplementedError
```

Dung Protocol de fake embedder va real embedder cung interface.

---

## 5. Fake Embedder Cho Unit Test

```python
class FakeEmbedder:
    model_name = "fake-embedding"

    def __init__(self, dimensions: int = 3) -> None:
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed_one(query)

    def _embed_one(self, text: str) -> list[float]:
        base = float(len(text) % 10) / 10.0
        return [base for _ in range(self.dimensions)]
```

Luu y:

```text
Fake vector chi dung test flow, khong dung retrieval quality.
```

---

## 6. Real NVIDIA/BGE-M3 Embedder Qua LangChain

```python
import os

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings


class LangChainNvidiaEmbedder:
    model_name = "baai/bge-m3"

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("NVIDIA_EMBEDDING_MODEL", self.model_name)
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("Missing NVIDIA_API_KEY")

        self.embedding = NVIDIAEmbeddings(
            model=self.model_name,
            api_key=api_key,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.embedding.embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        return self.embedding.embed_query(query)
```

Ghi chu:

```text
BGE-M3 dimension thuong la 1024.
Qdrant collection vector_size phai khop voi vector length thuc te.
Neu package LangChain NVIDIA doi signature, uu tien version package dang cai.
```

---

## 7. Embed Child Chunks Tu DB Rows

Sau guide 12, DB da co `DocumentChunk` rows.

Function de format input:

```python
from app.databases.models import DocumentChunk, DocumentVersion


def build_embedding_text_from_row(
    *,
    chunk: DocumentChunk,
    version: DocumentVersion,
    document_title: str,
    department: str,
    document_type: str,
) -> str:
    return build_embedding_text(
        title=document_title,
        department=department,
        document_type=document_type,
        heading_path=chunk.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        content=chunk.content,
    )
```

MVP chi select:

```text
chunk_type = child
index_status = not_indexed
```

---

## 8. Test Embedder

File:

```text
chatbot/backend/test/embedding/test_embedder.py
```

Tests:

```python
from app.embedding.embedder import FakeEmbedder, build_embedding_text


def test_build_embedding_text_contains_context():
    text = build_embedding_text(
        title="Quy trinh cap bang diem",
        department="PDT",
        document_type="quy_trinh",
        heading_path=["Quy trinh", "Buoc 1"],
        page_start=1,
        page_end=2,
        content="Noi dung chunk",
    )

    assert "Tai lieu: Quy trinh cap bang diem" in text
    assert "Muc: Quy trinh > Buoc 1" in text
    assert "Noi dung chunk" in text


def test_fake_embedder_returns_vectors():
    embedder = FakeEmbedder(dimensions=3)
    vectors = embedder.embed_texts(["abc", "abcd"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 3
```

Integration test that:

```python
import pytest

from app.embedding.embedder import LangChainNvidiaEmbedder


@pytest.mark.integration
def test_bge_m3_embedder_returns_vector():
    embedder = LangChainNvidiaEmbedder()
    vector = embedder.embed_query("test")

    assert len(vector) > 0
```

Integration test phai skip khi khong co `NVIDIA_API_KEY`:

```python
@pytest.mark.skip(reason="requires NVIDIA_API_KEY")
```

---

## 9. Update `__init__.py` Va `embeder.py`

File:

```text
chatbot/backend/app/embedding/__init__.py
```

```python
from app.embedding.embedder import (
    FakeEmbedder,
    LangChainNvidiaEmbedder,
    TextEmbedder,
    build_embedding_text,
)

__all__ = [
    "FakeEmbedder",
    "LangChainNvidiaEmbedder",
    "TextEmbedder",
    "build_embedding_text",
]
```

File:

```text
chatbot/backend/app/embedding/embeder.py
```

```python
from app.embedding.embedder import *  # noqa: F401,F403
```

---

## 10. Lenh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/embedding/test_embedder.py
```

---

## 11. Done Khi

- [ ] Co `embedder.py`.
- [ ] Co `TextEmbedder` Protocol.
- [ ] Co `FakeEmbedder` cho unit test.
- [ ] Co `LangChainNvidiaEmbedder` cho NVIDIA/BGE-M3.
- [ ] `build_embedding_text` them context title/heading/page.
- [ ] `embeder.py` re-export de tranh import cu bi loi.
- [ ] Unit test pass khong can tai model that.

---

## 12. Loi De Gap

### Loi: NVIDIA API key thieu hoac het credit

Xu ly:

```text
Dung FakeEmbedder trong unit test.
Chi chay LangChainNvidiaEmbedder trong integration test rieng khi co NVIDIA_API_KEY.
Dung cache trong 14A de tranh embed lai.
```

### Loi: vector dimension khong khop Qdrant

Xu ly:

```text
Tao Qdrant collection theo len(vector) thuc te tu embedder.
Khong hardcode 1024 trong test fake 3 dimensions.
```

### Loi: import `embeder` cu

Xu ly:

```text
Giu embeder.py wrapper re-export den khi refactor import xong.
```
