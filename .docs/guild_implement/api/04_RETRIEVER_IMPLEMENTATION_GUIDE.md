# 04. Implement Retriever (retrieval/retriever.py)

**Last Updated:** 2026-07-14

```text
Muc tieu file nay:
- Viet app/retrieval/retriever.py (hien RONG hoan toan, 0 dong).
- Noi 3 khoi da co san: embed_query() -> search_points() -> RetrievedChunk.
- MVP dense-only, lay truc tiep tu Qdrant payload, KHONG query PostgreSQL.
- Muc dich la co ham retrieve() chay duoc de guide RAG answer chain
  (app/llm/rag_chain.py) va router (POST /api/v1/rag/answer) goi vao,
  khong phai ban day du eligibility/hybrid nhu Guide 16.
```

File này chỉ làm `app/retrieval/retriever.py`. Router thật (`app/api/routes/rag.py`) và
answer chain (`app/llm/rag_chain.py`) là phần việc của guide khác trong bộ `api/`, **không**
làm ở đây.

---

## 1. Trạng Thái Hiện Tại (đã đọc code, không suy đoán)

Đã xác nhận bằng cách đọc trực tiếp:

```text
app/retrieval/retriever.py         -> RONG (0 dong). Chua co class/ham nao.
app/retrieval/eligibility.py       -> CHUA TON TAI. Guide 16/22 co thiet ke
                                       EligibilityPolicy nhung chua implement.
app/embedding/embedder.py          -> DA CO. Ham dung duoc:
                                       embed_query(query: str) -> list[float]
                                       embed_texts(texts: list[str]) -> list[list[float]]
                                       Doc os.getenv("NVIDIA_API_KEY"),
                                       os.getenv("NVIDIA_EMBEDDING_MODEL", "baai/bge-m3").
                                       Day la ham module-level (khong phai method cua
                                       class TextEmbedder/LangChainNvidiaEmbedder nhu
                                       Guide 16 mo ta - code THAT khac thiet ke cu).
app/vectorstore/qdrant_client.py   -> DA CO. get_qdrant_client() -> QdrantClient,
                                       doc os.getenv("QDRANT_URL", "http://localhost:6333"),
                                       os.getenv("QDRANT_API_KEY").
app/vectorstore/repository.py      -> DA CO day du. Ham dung duoc:
                                       COLLECTION_NAME = "ctu_chunks_bge_m3"
                                       VECTOR_NAME = "embedding"
                                       search_points(client, *, query_vector,
                                         collection_name=COLLECTION_NAME, top_k=5,
                                         filters: RetrievalFilter | None = None)
                                         -> list[QdrantSearchResult]
app/vectorstore/models.py          -> DA CO. RetrievalFilter (dataclass, frozen),
                                       QdrantChunkPayload (pydantic, dung khi upsert),
                                       QdrantSearchResult (dataclass: score: float,
                                         payload: dict).
app/core/settings_loader.py        -> DA CO RetrievalSettings(top_k=5, candidate_k=30,
                                       score_threshold=0.5) qua get_rag_settings()
                                       (lru_cache). Dung top_k nay lam default,
                                       khong hardcode lai so 5 o file moi.
```

`QdrantChunkPayload` (payload thực tế được lưu khi upsert, `app/vectorstore/repository.py::build_payload`)
có các field: `document_key`, `version_key`, `title`, `department`, `document_type`, `domain`,
`chunk_key`, `parent_chunk_key`, `chunk_type`, `heading_path`, `page_start`, `page_end`, `content`.
Đây là nguồn duy nhất có thật để build `RetrievedChunk` — không suy đoán field nào khác.

Guide 16 (`16_PART_I_RETRIEVAL_GUIDE.md`) thiết kế một bản đầy đủ hơn nhiều: `RetrievalResult` với
hydrate PostgreSQL, hybrid dense+sparse, structural expansion, eligibility filter qua
`EligibilityPolicy`. Guide 16 **chưa implement** (retriever.py đang rỗng), và các thành phần đó
(`app/retrieval/eligibility.py`, `search_sparse_documents()`, `build_langchain_qdrant_retriever()`)
đều chưa tồn tại trong code. File này viết một bản **rút gọn có chủ đích (MVP)**, không cố gắng
làm lại toàn bộ Guide 16 — xem mục 6 "Giới Hạn MVP So Với Guide 16/18" để biết rõ phần nào bị bỏ
qua và vì sao.

---

## 2. File Cần Tạo/Sửa

```text
chatbot/backend/app/retrieval/retriever.py       (SUA - dang rong, viet moi toan bo)
chatbot/backend/test/retrieval/test_retriever.py (TAO MOI)
```

Thư mục `chatbot/backend/test/retrieval/` đã tồn tại (rỗng, chỉ có `__pycache__` của một bản
test cũ đã bị xoá), chỉ cần thêm file test mới.

Không sửa `app/embedding/embedder.py`, `app/vectorstore/qdrant_client.py`,
`app/vectorstore/repository.py`, `app/vectorstore/models.py`.

---

## 3. Thiết Kế `RetrievedChunk`

`RetrievedChunk` là dataclass mới, khác tên và khác phạm vi so với `RetrievalResult` của Guide 16
(để không gây nhầm lẫn giữa bản MVP và bản đầy đủ). Field lấy thẳng từ `QdrantChunkPayload`, cộng
`score` từ `QdrantSearchResult`:

```text
document_key    -> payload["document_key"]
version_key     -> payload["version_key"]
title           -> payload["title"]
heading_path    -> payload["heading_path"]
page_start      -> payload["page_start"]
page_end        -> payload["page_end"]
content         -> payload["content"]
score           -> QdrantSearchResult.score (khong nam trong payload)
```

Không lấy `department`/`document_type`/`domain`/`chunk_key`/`parent_chunk_key`/`chunk_type` vào
`RetrievedChunk` vì yêu cầu của guide này chỉ liệt kê đúng 8 field trên — nếu answer chain
(`app/llm/rag_chain.py`) sau này cần thêm field để build citation chi tiết hơn, đó là thay đổi của
guide khác, không mở rộng tự do ở đây.

---

## 4. File Hoàn Chỉnh `app/retrieval/retriever.py`

```python
"""
Retrieval layer MVP: noi embedding cau hoi -> tim kiem Qdrant -> RetrievedChunk.

Flow:
    query (str)
    -> embed_query(query)               (app/embedding/embedder.py, da co)
    -> search_points(client, ...)       (app/vectorstore/repository.py, da co)
    -> list[RetrievedChunk]             (lay truc tiep tu Qdrant payload)

Day la ban RUT GON so voi thiet ke day du o
chatbot/.docs/guild_implement/16_PART_I_RETRIEVAL_GUIDE.md: khong hydrate PostgreSQL,
khong hybrid dense+sparse, khong structural expansion, khong eligibility filter.
Xem docstring cuoi file / guide nay muc 6 de biet ro pham vi.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from qdrant_client import QdrantClient

from app.core.settings_loader import get_rag_settings
from app.embedding.embedder import embed_query
from app.vectorstore.models import RetrievalFilter
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import COLLECTION_NAME, search_points


@dataclass(frozen=True)
class RetrievedChunk:
    """
    Mot ket qua truy xuat, lay truc tiep tu Qdrant payload (MVP dense-only).

    Khac RetrievalResult (Guide 16): khong co postgres_chunk_id, khong hydrate
    canonical content tu PostgreSQL, khong co citation/source_file/source_url.
    Content o day la content da luu trong Qdrant payload luc upsert
    (app/vectorstore/repository.py::build_payload), khong phai lay lai tu DB.
    """

    document_key: str
    version_key: str
    title: str
    heading_path: list[str]
    page_start: int
    page_end: int
    content: str
    score: float


def _to_retrieved_chunk(payload: dict, score: float) -> RetrievedChunk:
    """Map 1 QdrantSearchResult.payload (dict tho) sang RetrievedChunk."""
    return RetrievedChunk(
        document_key=payload.get("document_key", ""),
        version_key=payload.get("version_key", ""),
        title=payload.get("title", ""),
        heading_path=list(payload.get("heading_path") or []),
        page_start=payload.get("page_start", 1),
        page_end=payload.get("page_end", 1),
        content=payload.get("content", ""),
        score=score,
    )


async def retrieve(
    query: str,
    top_k: int | None = None,
    filters: RetrievalFilter | None = None,
    *,
    client: QdrantClient | None = None,
) -> list[RetrievedChunk]:
    """
    Retrieval dense-only cho MVP: embed query roi tim top_k chunk gan nhat trong Qdrant.

    Args:
        query: cau hoi tho cua nguoi dung. Rong/chi chua khoang trang -> tra [] ngay,
            khong goi embedding/Qdrant.
        top_k: so luong ket qua toi da. None -> lay tu
            get_rag_settings().retrieval.top_k (hien la 5), khong hardcode lai o day.
        filters: RetrievalFilter tuy chon (document_key/version_key/department/...).
            None -> search_points() dung RetrievalFilter() mac dinh, van luon loc
            chunk_type="child" (default field cua RetrievalFilter), khong tra ve
            parent chunk lan vao ket qua.
        client: QdrantClient tuy chon, chu yeu de test inject fake client. None ->
            tao qua get_qdrant_client() (doc QDRANT_URL/QDRANT_API_KEY tu env).

    Returns:
        list[RetrievedChunk], sap xep theo score giam dan (thu tu tra ve tu
        Qdrant query_points, khong sort lai o day).
    """
    normalized_query = query.strip()
    if not normalized_query:
        return []

    resolved_top_k = top_k if top_k is not None else get_rag_settings().retrieval.top_k
    qdrant_client = client if client is not None else get_qdrant_client()

    query_vector = await asyncio.to_thread(embed_query, normalized_query)

    search_results = await asyncio.to_thread(
        search_points,
        qdrant_client,
        query_vector=query_vector,
        collection_name=COLLECTION_NAME,
        top_k=resolved_top_k,
        filters=filters,
    )

    return [
        _to_retrieved_chunk(result.payload, result.score)
        for result in search_results
    ]
```

Lưu ý khi implement:

```text
- embed_query() va search_points() deu la ham dong bo (khong phai async), goi truc tiep
  cac SDK dong bo (NVIDIAEmbeddings.embed_query, QdrantClient.query_points). Ham retrieve()
  o day khai bao async theo yeu cau, nen dung asyncio.to_thread() de khong block event loop
  cua FastAPI khi co nhieu request dong thoi - khong goi truc tiep embed_query()/search_points()
  trong than ham async ma khong bao boc.
- top_k lay tu get_rag_settings().retrieval.top_k khi khong truyen, khong hardcode "= 5" o
  chu ky ham (dung dung setting da chot trong app/core/settings_loader.py, dung "or 5" fallback
  rai rac - dung dung gia tri tra ve tu get_rag_settings()).
- client la keyword-only, mac dinh None, chi de inject fake client khi test - production caller
  (rag_chain.py/router) khong can truyen, se tu tao qua get_qdrant_client().
- filters=None van an toan: search_points(..., filters=None) -> build_context_filter(None)
  (app/vectorstore/repository.py) tu dong dung RetrievalFilter() voi chunk_type="child" mac dinh,
  khong can retrieve() tu tao RetrievalFilter() rong o day.
```

---

## 5. Test/Kiểm Thử

File: `chatbot/backend/test/retrieval/test_retriever.py`

Không cần Qdrant/NVIDIA thật — monkeypatch trực tiếp `embed_query` và `search_points` đã được
import vào module `app.retrieval.retriever`.

```python
import pytest

import app.retrieval.retriever as retriever_module
from app.retrieval.retriever import RetrievedChunk, retrieve
from app.vectorstore.models import QdrantSearchResult, RetrievalFilter


class _FakeQdrantClient:
    """Client gia, khong ket noi Qdrant thuc."""


@pytest.mark.asyncio
async def test_retrieve_returns_empty_list_for_blank_query(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("khong duoc goi embed_query() khi query rong")

    monkeypatch.setattr(retriever_module, "embed_query", fail_if_called)

    results = await retrieve("   ")

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_maps_payload_to_retrieved_chunk(monkeypatch):
    monkeypatch.setattr(retriever_module, "embed_query", lambda query: [0.1, 0.2, 0.3])

    def fake_search_points(client, *, query_vector, collection_name, top_k, filters):
        assert query_vector == [0.1, 0.2, 0.3]
        assert top_k == 3
        return [
            QdrantSearchResult(
                score=0.87,
                payload={
                    "document_key": "qd-3266",
                    "version_key": "qd-3266-2024",
                    "title": "Quy dinh cong tac hoc vu",
                    "heading_path": ["Chuong 1", "Dieu 5"],
                    "page_start": 2,
                    "page_end": 3,
                    "content": "Sinh vien can nop don theo mau...",
                },
            )
        ]

    monkeypatch.setattr(retriever_module, "search_points", fake_search_points)

    results = await retrieve(
        "dieu kien xin bang diem",
        top_k=3,
        client=_FakeQdrantClient(),
    )

    assert results == [
        RetrievedChunk(
            document_key="qd-3266",
            version_key="qd-3266-2024",
            title="Quy dinh cong tac hoc vu",
            heading_path=["Chuong 1", "Dieu 5"],
            page_start=2,
            page_end=3,
            content="Sinh vien can nop don theo mau...",
            score=0.87,
        )
    ]


@pytest.mark.asyncio
async def test_retrieve_uses_default_top_k_from_settings(monkeypatch):
    from app.core.settings_loader import get_rag_settings

    captured = {}

    monkeypatch.setattr(retriever_module, "embed_query", lambda query: [0.0])

    def fake_search_points(client, *, query_vector, collection_name, top_k, filters):
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(retriever_module, "search_points", fake_search_points)

    await retrieve("dieu kien xin bang diem", client=_FakeQdrantClient())

    assert captured["top_k"] == get_rag_settings().retrieval.top_k


@pytest.mark.asyncio
async def test_retrieve_forwards_filters_to_search_points(monkeypatch):
    captured = {}

    monkeypatch.setattr(retriever_module, "embed_query", lambda query: [0.0])

    def fake_search_points(client, *, query_vector, collection_name, top_k, filters):
        captured["filters"] = filters
        return []

    monkeypatch.setattr(retriever_module, "search_points", fake_search_points)

    given_filters = RetrievalFilter(document_key="qd-3266")
    await retrieve(
        "dieu kien xin bang diem",
        filters=given_filters,
        client=_FakeQdrantClient(),
    )

    assert captured["filters"] is given_filters
```

Cần `pytest-asyncio` (đã có trong `requirements.txt`). Nếu `pyproject.toml`/`pytest.ini` chưa cấu
hình `asyncio_mode`, dùng marker `@pytest.mark.asyncio` như trên (marker rõ ràng thay vì mode auto,
tránh ảnh hưởng test đồng bộ khác trong cùng project).

Lệnh chạy test:

```bash
cd chatbot/backend
pytest test/retrieval/test_retriever.py -v
```

### 5.1 Kiểm thử thủ công (chưa có router, không dùng curl được)

Guide này chưa tạo `app/api/routes/rag.py`, nên `retrieve()` chưa có endpoint HTTP để gọi bằng
`curl`. Kiểm thử thủ công tạm thời qua một script Python nhỏ, cần `QDRANT_URL` chạy được và
`NVIDIA_API_KEY` hợp lệ trong `.env`:

```python
# chay tay: python -c "..." hoac luu vao file script.py roi chay
import asyncio

from app.retrieval.retriever import retrieve


async def main() -> None:
    results = await retrieve("Em muon xin bang diem thi can gi?", top_k=3)
    for chunk in results:
        print(f"[{chunk.score:.3f}] {chunk.title} - {chunk.document_key}")
        print(chunk.content[:200])
        print("---")


asyncio.run(main())
```

Kết quả mong đợi: in ra tối đa 3 chunk có `score` giảm dần, không lỗi kết nối Qdrant/NVIDIA. Nếu
collection `ctu_chunks_bge_m3` chưa có dữ liệu (chưa chạy ingestion), `results` sẽ là `[]` — đây là
hành vi đúng, không phải lỗi của `retrieve()`.

---

## 6. Giới Hạn MVP So Với Guide 16/18

```text
KHONG hydrate PostgreSQL:
    Content/title/page_start/page_end lay truc tiep tu Qdrant payload, KHONG
    query lai app/databases/models/DocumentChunk. Guide 16 coi Qdrant khong
    phai canonical source of truth va bat buoc hydrate tu PostgreSQL - MVP nay
    co tinh danh doi de co API chay duoc truoc, chap nhan content co the
    lech nhe voi PostgreSQL neu payload cu chua duoc re-upsert sau khi
    canonical content doi.

KHONG hybrid dense + sparse (FTS/BM25):
    Chi co dense vector search qua search_points(). Khong co
    search_sparse_documents(), khong co reciprocal_rank_fusion().

KHONG structural expansion:
    Khong lay parent/sibling/split neighbor. Moi ket qua deu la direct hit
    tu Qdrant, khong co truong expansion_reason.

KHONG eligibility filter (review_status=approved/rag_status=published/is_latest):
    Day la thieu sot QUAN TRONG can xu ly truoc khi dua ra production cho
    sinh vien - hien tai retrieve() co the tra ve chunk chua duoc duyet hoac
    chua publish, vi RetrievalFilter (app/vectorstore/models.py) khong co
    field nao cho review_status/rag_status/is_latest.
    Tham khao Contract 10 va Guide 22, sau do Guide 16
    muc 8 "Eligibility Filter O Dau?": nguon chan ly du kien nam o
    app/retrieval/eligibility.py::EligibilityPolicy (module nay CHUA TON TAI).
    Khi module do duoc viet, retrieve() trong file nay phai duoc sua lai de
    goi build_eligibility_filter()/EligibilityPolicy truoc khi goi
    search_points(), khong tu dinh nghia dieu kien status rieng. Day la viec
    de lai cho giai doan 2, khong lam trong guide nay.
```

Không được coi `retrieve()` ở đây là bản production hoàn chỉnh — mục đích duy nhất là cho router
`POST /api/v1/rag/answer` (guide khác) và `rag_chain.py` (guide khác) có một hàm thật để gọi, thay
vì file rỗng.

---

## 7. Không Làm Trong File Này

```text
Khong tao app/retrieval/eligibility.py.
Khong sua app/embedding/embedder.py, app/vectorstore/qdrant_client.py,
  app/vectorstore/repository.py, app/vectorstore/models.py.
Khong tao app/api/routes/rag.py hay app/llm/rag_chain.py.
Khong them auth/JWT.
Khong them field ngoai 8 field cua RetrievedChunk da liet ke o muc 3.
```

---

## 8. Done Khi

- [ ] `app/retrieval/retriever.py` tồn tại, export `RetrievedChunk` và `retrieve()`.
- [ ] `RetrievedChunk` là `@dataclass(frozen=True)` với đúng 8 field: `document_key`,
  `version_key`, `title`, `heading_path`, `page_start`, `page_end`, `content`, `score`.
- [ ] `retrieve("")` hoặc `retrieve("   ")` trả `[]` ngay, không gọi `embed_query()`/`search_points()`.
- [ ] `retrieve()` dùng `top_k` từ `get_rag_settings().retrieval.top_k` khi không truyền tham số,
  không hardcode số khác.
- [ ] `retrieve()` gọi `embed_query()` (đã có ở `app/embedding/embedder.py`) và `search_points()`
  (đã có ở `app/vectorstore/repository.py`) qua `asyncio.to_thread()`, không gọi trực tiếp trong
  thân hàm async.
- [ ] `retrieve()` nhận `filters: RetrievalFilter | None` và forward đúng xuống `search_points()`.
- [ ] `retrieve()` nhận `client: QdrantClient | None` tuỳ chọn để test có thể inject fake client.
- [ ] `test/retrieval/test_retriever.py` chạy pass với `pytest`, không cần Qdrant/NVIDIA thật.
- [ ] Guide có ghi rõ (mục 6) những gì bị bỏ qua so với Guide 16/18 (hydrate PostgreSQL, hybrid
  search, structural expansion, eligibility filter) — không im lặng bỏ qua eligibility.
- [ ] Không sửa file nào trong `app/embedding/`, `app/vectorstore/` ngoài việc import.

---

## 9. Phụ Thuộc / Thứ Tự Làm Trước

```text
Khong phu thuoc guide nao khac de viet duoc file nay - app/embedding/embedder.py,
app/vectorstore/qdrant_client.py, app/vectorstore/repository.py, app/vectorstore/models.py,
app/core/settings_loader.py deu da co san va da doc truoc khi viet guide nay.

De retrieve() thuc su duoc goi tu API cong khai, can lam sau:
- Guide tao app/llm/rag_chain.py (answer_question()) - se import retrieve() tu file nay
  de lay context truoc khi goi LLM.
- Guide tao app/api/routes/rag.py (POST /api/v1/rag/answer) - router se goi answer_question(),
  khong goi retrieve() truc tiep.
- Guide viet app/retrieval/eligibility.py (chua ton tai trong bo guide hien tai) - can lam
  truoc khi dua retrieve() vao production cho sinh vien thuc, de bo sung eligibility filter
  da neu o muc 6.

File nay khong phu thuoc 03_RAG_ANSWER_SCHEMA_GUIDE.md (schema Pydantic doc lap), nhung
RagAnswerResponse.citations o guide 03 se can du lieu tu ket qua cua retrieve() (qua rag_chain.py)
de build Citation.document_id/version_id - hai gia tri nay KHONG co san trong RetrievedChunk
(chi co document_key/version_key dang string), can mot buoc resolve string key -> PK int rieng
o tang hydrate/rag_chain, khong lam trong file nay.
```
