# 14. Part G - Hướng Dẫn Implement Embedding

**Last Updated:** 2026-06-20

> **Trước khi embed:** chunks phải được tạo sau pre-chunk structural parsing theo `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md`. Bước này phải làm trước chunking, vì item/page/table/code sai sẽ làm sai `heading_path`, `item_path`, `legal_unit_type`, `page_start/page_end` của child trước khi embed.

File này tách chi tiết từ guide 07, phần G.

Mục tiêu:

```text
Tao abstraction embedder theo LangChain
format text dau vao cho chunk
co fake embedder de test nhanh
co real NVIDIA/BGE-M3 embedder cho integration
```

MVP chỉ embed child chunks.

Nếu đã làm smoke test theo:

```text
chatbot/.docs/guild_implement/14A_EMBEDDING_RETRIEVAL_SMOKE_TEST_GUIDE.md
```

thì guide này không phải cài lại từ đầu. Chuyển các phần đã test tốt sang module chính thức:

```text
14A embed_texts() -> app/embedding/embedder.py
14A model choice/vector dimension -> TextEmbedder/LangChainNvidiaEmbedder
14A query embedding -> embed_query()
```

Khác biệt quan trọng:

```text
14A doc Markdown va chunk truc tiep de smoke test.
Guide 14 production khong doc Markdown, khong chunk.
Guide 14 nhan chunks/DB rows tu pipeline sau guide 12/13.
Da chot RAG pipeline di theo LangChain, nen real embedder production dung LangChain NVIDIA embeddings.
```

---

## 1. File Cần Tạo/Sửa

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/embedding/__init__.py
chatbot/backend/app/embedding/embeder.py
chatbot/backend/test/embedding/test_embedder.py
```

File `embeder.py` đang sai chính tả. Không cần xóa ngay. Tạo `embedder.py`, rồi để `embeder.py` re-export.

---

## 2. Requirements

File:

```text
chatbot/backend/requirements.txt
```

Thêm:

```text
numpy>=1.26
langchain-nvidia-ai-endpoints
```

Unit test dùng fake embedder. Integration test cần `NVIDIA_API_KEY`.

---

## 3. Data Input Cho Embedding

Không embed mọi raw content. Nên thêm context:

```text
Tai lieu: <title>
Don vi: <department>
Loai: <document_type>
Muc: <heading_path>
Don vi phap ly: <legal_unit_type>
Duong dan muc: <item_path>
Trang: <page_start>-<page_end>

<content>
```

Raw child content phải giữ nguyên. `embedding_text` chỉ là text phụ để embed, không ghi đè `content`.
Không đưa page marker vào `embedding_text`. Không thêm thông tin suy diễn.

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
    item_path: list[str] | None = None,
    legal_unit_type: str = "none",
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
    if legal_unit_type and legal_unit_type != "none":
        lines.append(f"Don vi phap ly: {legal_unit_type}")
    if item_path:
        lines.append(f"Duong dan muc: {' > '.join(item_path)}")
    if page:
        lines.append(page)

    lines.append("")
    lines.append(remove_page_markers(content).strip())
    return "\n".join(line for line in lines if line is not None)
```

Helper:

```python
import re

PAGE_RE = re.compile(r"<!--\s*page:\s*\d+\s*-->", re.IGNORECASE)


def remove_page_markers(text: str) -> str:
    return PAGE_RE.sub("", text)
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

Dùng Protocol để fake embedder và real embedder cùng interface.

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

Lưu ý:

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

Ghi chú:

```text
BGE-M3 dimension thuong la 1024.
Qdrant collection vector_size phai khop voi vector length thuc te.
Neu package LangChain NVIDIA doi signature, uu tien version package dang cai.
```

---

## 7. Embed Child Chunks Từ DB Rows

Sau guide 12, DB đã có `DocumentChunk` rows.

Function để format input:

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
        item_path=chunk.extra_metadata.get("item_path", []) if chunk.extra_metadata else [],
        legal_unit_type=(
            chunk.extra_metadata.get("legal_unit_type", "none")
            if chunk.extra_metadata
            else "none"
        ),
    )
```

MVP chỉ select:

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
        item_path=["Khoan 1", "Diem a)"],
        legal_unit_type="point",
    )

    assert "Tai lieu: Quy trinh cap bang diem" in text
    assert "Muc: Quy trinh > Buoc 1" in text
    assert "Duong dan muc: Khoan 1 > Diem a)" in text
    assert "Noi dung chunk" in text


def test_fake_embedder_returns_vectors():
    embedder = FakeEmbedder(dimensions=3)
    vectors = embedder.embed_texts(["abc", "abcd"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 3
```

Integration test thật:

```python
import pytest

from app.embedding.embedder import LangChainNvidiaEmbedder


@pytest.mark.integration
def test_bge_m3_embedder_returns_vector():
    embedder = LangChainNvidiaEmbedder()
    vector = embedder.embed_query("test")

    assert len(vector) > 0
```

Integration test phải skip khi không có `NVIDIA_API_KEY`:

```python
@pytest.mark.skip(reason="requires NVIDIA_API_KEY")
```

---

## 9. Update `__init__.py` Và `embeder.py`

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

## 10. Lệnh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/embedding/test_embedder.py
```

---

## 11. Done Khi

- [ ] Có `embedder.py`.
- [ ] Có `TextEmbedder` Protocol.
- [ ] Có `FakeEmbedder` cho unit test.
- [ ] Có `LangChainNvidiaEmbedder` cho NVIDIA/BGE-M3.
- [ ] `build_embedding_text` thêm context title/heading/page.
- [ ] `embeder.py` re-export để tránh import cũ bị lỗi.
- [ ] Unit test pass không cần tải model thật.

---

## 12. Lỗi Dễ Gặp

### Lỗi: NVIDIA API key thiếu hoặc hết credit

Xử lý:

```text
Dung FakeEmbedder trong unit test.
Chi chay LangChainNvidiaEmbedder trong integration test rieng khi co NVIDIA_API_KEY.
Dung cache trong 14A de tranh embed lai.
```

### Lỗi: vector dimension không khớp Qdrant

Xử lý:

```text
Tao Qdrant collection theo len(vector) thuc te tu embedder.
Khong hardcode 1024 trong test fake 3 dimensions.
```

### Lỗi: import `embeder` cũ

Xử lý:

```text
Giu embeder.py wrapper re-export den khi refactor import xong.
```
