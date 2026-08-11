# 21. Runtime Settings Guide

**Mục tiêu:** gom các tham số tuning như chunk size, overlap, retrieval top_k vào config có default rõ ràng.

Không dùng pattern:

```python
child_chunk_size = settings.chunking.child_chunk_size or 1000
top_k = settings.retrieval.top_k or 5
```

Vì `or` sẽ âm thầm che lỗi config (`0`, `None`, typo). Default phải nằm trong settings model.

---

## Settings Mặc Định

File:

```text
app/core/settings_loader.py
```

Mẫu:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ChunkingSettings:
    child_chunk_size: int = 1000
    child_chunk_overlap: int = 100


@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int = 5
    candidate_k: int = 30


@dataclass(frozen=True)
class AppSettings:
    chunking: ChunkingSettings = field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)
```

YAML chỉ override, không bắt buộc khai báo đủ:

```yaml
chunking:
  child_chunk_size: 1000
  child_chunk_overlap: 100

retrieval:
  top_k: 5
  candidate_k: 30
```

Nếu thiếu key, dùng default trong dataclass. Nếu key có giá trị sai kiểu hoặc không hợp lệ, raise lỗi rõ ràng, không fallback bằng `or`.

---

## Load Settings

`load_settings()` là nơi duy nhất đọc YAML và apply override. Không parse YAML rải rác trong chunker/retriever.

```python
def load_settings(path: str | Path) -> AppSettings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    settings = AppSettings(
        chunking=ChunkingSettings(**data.get("chunking", {})),
        retrieval=RetrievalSettings(**data.get("retrieval", {})),
    )
    validate_settings(settings)
    return settings
```

Nếu app cần dùng nhiều nơi, thêm cache loader:

```python
@lru_cache
def get_rag_settings() -> AppSettings:
    return load_settings(Path("config/runtime.yaml"))
```

> `get_rag_settings()` chỉ lấy cấu hình runtime chung cho RAG. Metadata YAML của từng document vẫn đọc bằng markdown reader riêng, không đưa vào runtime settings.

---

## Validation

Nên validate sau khi load:

```python
def validate_settings(settings: AppSettings) -> None:
    if settings.chunking.child_chunk_size <= 0:
        raise ValueError("chunking.child_chunk_size must be > 0")
    if settings.chunking.child_chunk_overlap < 0:
        raise ValueError("chunking.child_chunk_overlap must be >= 0")
    if settings.chunking.child_chunk_overlap >= settings.chunking.child_chunk_size:
        raise ValueError("chunking.child_chunk_overlap must be smaller than child_chunk_size")
    if settings.retrieval.top_k <= 0:
        raise ValueError("retrieval.top_k must be > 0")
    if settings.retrieval.candidate_k < settings.retrieval.top_k:
        raise ValueError("retrieval.candidate_k must be >= retrieval.top_k")
```

---

## Usage

Chunker:

```python
settings = get_rag_settings()
chunk_result = chunk_markdown_body(
    body=body,
    document_key=document_key,
    version_key=version_key,
    child_chunk_size=settings.chunking.child_chunk_size,
    child_chunk_overlap=settings.chunking.child_chunk_overlap,
)
```

Retriever:

```python
settings = get_rag_settings()
results = await retriever.search_resolved_query(
    session,
    query=resolved_query,
    document_key=decision.document_key,
    version_key=decision.version_key,
    top_k=settings.retrieval.top_k,
)
```

`resolved_query` chỉ được tạo sau `complete_or_clarify_query()`. Greeting/clarification không gọi Retriever. Function signatures may keep explicit parameters for tests, but callers should pass values from `settings`.

---

## Không Đưa Vào Settings Này

Không đưa DB schema `css` vào runtime settings nếu schema cố định. `MetaData(schema="css")` trong `app/databases/base.py` là structural DB contract, không phải tuning runtime.

Không đưa metadata YAML fields vào runtime settings.
