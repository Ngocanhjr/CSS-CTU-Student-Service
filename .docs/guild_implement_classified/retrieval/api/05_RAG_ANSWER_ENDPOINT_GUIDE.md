# 05. Endpoint POST /api/v1/rag/answer

**Last Updated:** 2026-07-14

```text
Muc tieu file nay:
- Tao app/api/rag.py (CHUA TON TAI), router POST /api/v1/rag/answer.
- Noi retriever.retrieve() (guide 04) + RAG_ANSWER_PROMPT (da co, app/llm/prompts.py)
  + LLM client moi (app/llm/generator.py) thanh 1 luong tra loi hoan chinh.
- Neu retrieve() tra 0 chunk: tra cau tra loi co dinh, citations rong,
  KHONG goi LLM (tiet kiem cost, tranh hallucination).
- Resolve RetrievedChunk.document_key/version_key (string) sang
  Citation.document_id/version_id (int PK) qua PostgreSQL - buoc con thieu
  duoc guide 03 danh dau lai, lam o day.
```

File nay phu thuoc truc tiep vao guide 03 (`03_RAG_ANSWER_SCHEMA_GUIDE.md`, schema
`RagAnswerRequest`/`Citation`/`RagAnswerResponse`) va guide 04
(`04_RETRIEVER_IMPLEMENTATION_GUIDE.md`, ham `retrieve()`/`RetrievedChunk`). Ca hai
guide do **chi la thiet ke**, code thuc (`app/schemas/rag.py`, noi dung thuc su cua
`app/retrieval/retriever.py`) **can duoc viet truoc** khi file nay chay duoc - xem
muc 10 "Phu Thuoc / Thu Tu Lam Truoc".

---

## 1. Trang Thai Hien Tai (da doc code, khong suy doan)

```text
app/api/rag.py                 -> CHUA TON TAI, phai tao moi.
app/api/health.py              -> RONG (0 dong), chua co route (guide 01/02).
app/api/reference_data.py      -> DA CO (guide 06), dung lam mau convention:
                                   APIRouter(tags=[...]) khong tu khai bao
                                   prefix="/api/v1", route path khong prefix,
                                   dat truc tiep trong app/api/, KHONG dat
                                   trong app/api/routes/ (thu muc nay van dang rong).
app/main.py                    -> Sau guide 01/02/06: da co FastAPI(), CORS,
                                   lifespan warm-up embedding,
                                   include_router(health_router),
                                   include_router(reference_data_router, prefix="/api/v1").
                                   Dong import/include_router cho rag/documents/
                                   versions/ingestion van la comment placeholder.
app/schemas/rag.py             -> CHUA TON TAI trong code thuc, chi co thiet ke
                                   day du trong guide 03 (RagAnswerRequest,
                                   Citation, RagAnswerResponse). Guide nay GIA DINH
                                   file do da duoc viet dung nhu guide 03 mo ta.
app/retrieval/retriever.py     -> RONG (0 dong) trong code thuc, chi co thiet ke
                                   day du trong guide 04 (retrieve(), RetrievedChunk
                                   voi 8 field: document_key, version_key, title,
                                   heading_path, page_start, page_end, content, score).
                                   Guide nay GIA DINH file do da duoc viet dung nhu
                                   guide 04 mo ta.
app/llm/prompts.py             -> DA CO thuc su. RAG_ANSWER_PROMPT =
                                   ChatPromptTemplate.from_template(template) voi
                                   bien {context} va {question} (KHONG phai
                                   from_messages nhu guide 18 mo ta - day la code
                                   THAT, dung nguyen, khong sua template).
app/llm/generator.py            -> RONG (0 dong). Phai them get_chat_llm().
app/llm/rag_chain.py            -> RONG (0 dong). Phai them build_context_block(),
                                   resolve_version_refs(), build_citations(),
                                   generate_answer().
app/core/api_settings.py       -> CHUA duoc xac nhan ton tai trong lan doc nay -
                                   guide nay GIA DINH get_api_settings().llm da co
                                   theo thiet ke guide 02 (provider/api_key/chat_model).
                                   Neu file chua duoc viet, phai lam guide 02 truoc.
app/databases/models/documents.py
                                -> DocumentVersion co san: id (PK), document_id (FK
                                   toi documents.id), version_key (unique),
                                   canonical_markdown_path (Text, default "").
app/databases/session.py       -> get_session() (async generator) da co, dung
                                   duoc lam FastAPI Depends() ngay.
```

Ket luan: day la **phan hoan toan moi** (router + 2 ham moi trong `app/llm/`),
noi lai 3 khoi da duoc THIET KE (guide 03/04) va 1 khoi DA CO THAT (`prompts.py`).

---

## 2. File Can Tao/Sua

```text
chatbot/backend/app/llm/generator.py       (SUA - dang rong, them get_chat_llm())
chatbot/backend/app/llm/rag_chain.py       (SUA - dang rong, them 4 ham)
chatbot/backend/app/api/rag.py             (MOI - tao)
chatbot/backend/app/main.py                (SUA - them include_router cho rag)
chatbot/backend/test/llm/test_rag_chain.py (MOI - tao)
chatbot/backend/test/api/test_rag.py       (MOI - tao)
```

Khong sua `app/llm/prompts.py`, `app/retrieval/retriever.py`, `app/schemas/rag.py`
(gia dinh da co dung nhu guide 04/03 - neu sai thiet ke, sua o guide do, khong sua
"ngau" trong guide nay).

---

## 3. `app/llm/generator.py` - Khoi Tao LLM Client

File dang rong. Theo de xuat da chot huong o guide 02 muc 4 (huong A - dung
`ChatNVIDIA` de nhat quan voi `embedder.py`, cung dung `langchain_nvidia_ai_endpoints`),
doc cau hinh qua `get_api_settings().llm` (guide 02), khong tu `os.getenv()` rieng
trong file nay:

```python
"""
Khoi tao LLM client dung cho RAG answer chain.

Theo quyet dinh de xuat o guide 02 (02_SETTINGS_ENV_CORS_GUIDE.md muc 4):
dung ChatNVIDIA (langchain_nvidia_ai_endpoints) de nhat quan voi
app/embedding/embedder.py (cung dung NVIDIA_API_KEY/NVIDIA NIM).
"""

from __future__ import annotations

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.core.api_settings import get_api_settings


def get_chat_llm() -> ChatNVIDIA:
    """
    Tra ve ChatNVIDIA instance da cau hinh model/api_key tu ApiSettings.llm.

    Raise ValueError ro rang neu thieu api_key hoac provider khong ho tro,
    khong fallback gia tri gia - loi phai xuat hien ngay khi router thuc
    su can goi LLM (khong phai luc import module).
    """
    llm_settings = get_api_settings().llm
    if llm_settings.provider != "nvidia":
        raise ValueError(
            f"get_chat_llm() hien chi ho tro provider 'nvidia', dang la "
            f"{llm_settings.provider!r}"
        )
    if not llm_settings.api_key:
        raise ValueError("LLM_API_KEY environment variable is not set.")

    return ChatNVIDIA(model=llm_settings.chat_model, api_key=llm_settings.api_key)
```

Luu y:

```text
- get_chat_llm() KHONG dung @lru_cache: ChatNVIDIA la client co the giu ket noi/
  session ben trong, va guide nay uu tien de moi request tu tao instance moi qua
  Depends() (xem muc 5) de test de inject fake LLM hon, giong cach retrieve()
  (guide 04) nhan client: QdrantClient | None qua keyword-only param thay vi cache
  global. Neu sau nay do dat hieu nang can cache client dung mot lan, do la thay doi
  co chu dich rieng, khong lam am tham o day.
- Khong dat get_chat_llm() trong app/core/api_settings.py (module do chi doc cau
  hinh, khong import langchain_nvidia_ai_endpoints) - dung theo dung quyet dinh da
  ghi trong guide 02 muc 4.
```

---

## 4. `app/llm/rag_chain.py` - Noi Retrieval + Prompt + LLM + Citation

File dang rong. Bon viec chinh: (a) build context block tu `list[RetrievedChunk]`
de dua vao `RAG_ANSWER_PROMPT`, (b) resolve `document_key`/`version_key` (string)
sang `document_id`/`version_id` (int PK) qua PostgreSQL, (c) build `list[Citation]`,
(d) `generate_answer()` goi LLM va tra `(answer, citations)`.

### 4.1 Vi sao can resolve document_key/version_key -> id

`RetrievedChunk` (guide 04) chi co `document_key`/`version_key` dang string (lay
truc tiep tu Qdrant payload). `Citation` (guide 03) yeu cau `document_id: int`/
`version_id: int` (PK thuc trong bang `documents`/`document_versions`). Day la
buoc hydrate toi thieu **bat buoc phai co** o guide nay - khong bo qua, vi
`Citation.document_id`/`version_id` la `Field(gt=0)`, khong co gia tri hop le nao
khac ngoai PK thuc.

```python
async def resolve_version_refs(
    session: AsyncSession,
    version_keys: list[str],
) -> dict[str, DocumentVersion]:
    """
    Tra ve dict version_key -> DocumentVersion (co the thieu key neu
    version_key khong con ton tai trong DB - vi du Qdrant payload cu chua
    duoc don dep sau khi xoa version). Load kem Document qua joinedload
    de lay duoc document_id/title trong cung 1 query, tranh N+1.
    """
    if not version_keys:
        return {}

    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.version_key.in_(version_keys))
        .options(joinedload(DocumentVersion.document))
    )
    result = await session.execute(stmt)
    rows = result.scalars().unique().all()
    return {row.version_key: row for row in rows}
```

### 4.2 Build Citation Tu RetrievedChunk + DocumentVersion

```python
def build_citations(
    chunks: list[RetrievedChunk],
    version_by_key: dict[str, DocumentVersion],
    *,
    snippet_length: int = 240,
) -> list[Citation]:
    """
    Ghep RetrievedChunk (Qdrant) voi DocumentVersion (Postgres) de tao Citation.

    Chunk nao khong resolve duoc version_key (khong con trong DB) se bi BO QUA
    khoi danh sach citation, khong raise loi - day la du lieu Qdrant lech voi
    Postgres (payload cu chua duoc re-index), khong phai loi cua request hien tai.
    Khong lam sap chain answer vi 1 chunk "mo côi" con lai.
    """
    citations: list[Citation] = []
    for chunk in chunks:
        version = version_by_key.get(chunk.version_key)
        if version is None:
            continue

        citations.append(
            Citation(
                document_id=version.document_id,
                version_id=version.id,
                title=chunk.title or version.title or version.document.title,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=" > ".join(chunk.heading_path),
                source_file=version.canonical_markdown_path,
                quote_snippet=chunk.content[:snippet_length].strip(),
            )
        )
    return citations
```

Luu y:

```text
- section_title cua Citation (guide 03) la 1 string, nhung heading_path cua
  RetrievedChunk (guide 04) la list[str]. Noi bang " > ", khong bia them cot
  DB moi - dung dung du lieu da co trong RetrievedChunk.
- title fallback 3 tang: chunk.title (tu Qdrant payload) -> version.title ->
  version.document.title, vi DocumentVersion.title co default="" (co the rong).
- source_file lay tu DocumentVersion.canonical_markdown_path (Text, default ""),
  dung field co thuc, khong bia "source_file" moi trong DB nhu guide 03 muc 4
  da luu y ro.
- page_start/page_end cua RetrievedChunk (guide 04) khai bao la int khong nullable
  (default 1 khi payload thieu), trong khi Citation.page_start/page_end la
  int | None. Truyen thang duoc vi int luon la subtype hop le cua int | None.
```

### 4.3 Build Context Block Cho Prompt

`RAG_ANSWER_PROMPT` (da co that, `app/llm/prompts.py`) dung `.from_template()` voi
2 bien `{context}`/`{question}` - khac thiet ke `from_messages` cua guide 18. Ham
build context o day phai tra ve **1 string** (khong phai list message), khop dung
voi bien `{context}` cua template that:

```python
def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """
    Ghep list[RetrievedChunk] thanh 1 string dua vao bien {context} cua
    RAG_ANSWER_PROMPT (app/llm/prompts.py, dung .from_template(), KHONG phai
    .from_messages() nhu thiet ke o guide 18 - code that khac thiet ke cu,
    ham nay phai khop voi code that).
    """
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else ""
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"Tai lieu: {chunk.title}",
                    f"Muc: {heading}",
                    f"Trang: {chunk.page_start}-{chunk.page_end}",
                    "Noi dung:",
                    chunk.content,
                ]
            )
        )
    return "\n\n".join(blocks)
```

### 4.4 `generate_answer()` - Ham Chinh Router Se Goi

```python
async def generate_answer(
    session: AsyncSession,
    llm: ChatNVIDIA,
    query: str,
    chunks: list[RetrievedChunk],
) -> tuple[str, list[Citation]]:
    """
    Sinh cau tra loi cuoi cung tu list[RetrievedChunk] da retrieval.

    KHONG tu goi retrieve() o day - router (app/api/rag.py) chiu trach nhiem
    goi retrieve() truoc, ham nay chi nhan chunks san co. Ly do tach rieng:
    router can biet ro luc nao 0 chunk de tra early-return co dinh (muc 5.2)
    ma KHONG goi LLM, thay vi giau logic do ben trong generate_answer().
    """
    version_keys = list(dict.fromkeys(chunk.version_key for chunk in chunks))
    version_by_key = await resolve_version_refs(session, version_keys)
    citations = build_citations(chunks, version_by_key)

    context_block = build_context_block(chunks)
    chain = RAG_ANSWER_PROMPT | llm | StrOutputParser()
    answer = await chain.ainvoke({"context": context_block, "question": query})

    return answer, citations
```

File hoan chinh `app/llm/rag_chain.py`:

```python
"""
Noi retrieval (app/retrieval/retriever.py) + prompt (app/llm/prompts.py) +
LLM (app/llm/generator.py) thanh 1 luong sinh cau tra loi RAG hoan chinh.

Khong goi retrieve() truc tiep trong module nay - router (app/api/rag.py)
goi retrieve() truoc, roi moi goi generate_answer() voi chunks da co san.
"""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.databases.models import DocumentVersion
from app.llm.prompts import RAG_ANSWER_PROMPT
from app.retrieval.retriever import RetrievedChunk
from app.schemas.rag import Citation


async def resolve_version_refs(
    session: AsyncSession,
    version_keys: list[str],
) -> dict[str, DocumentVersion]:
    if not version_keys:
        return {}

    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.version_key.in_(version_keys))
        .options(joinedload(DocumentVersion.document))
    )
    result = await session.execute(stmt)
    rows = result.scalars().unique().all()
    return {row.version_key: row for row in rows}


def build_citations(
    chunks: list[RetrievedChunk],
    version_by_key: dict[str, DocumentVersion],
    *,
    snippet_length: int = 240,
) -> list[Citation]:
    citations: list[Citation] = []
    for chunk in chunks:
        version = version_by_key.get(chunk.version_key)
        if version is None:
            continue

        citations.append(
            Citation(
                document_id=version.document_id,
                version_id=version.id,
                title=chunk.title or version.title or version.document.title,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=" > ".join(chunk.heading_path),
                source_file=version.canonical_markdown_path,
                quote_snippet=chunk.content[:snippet_length].strip(),
            )
        )
    return citations


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else ""
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"Tai lieu: {chunk.title}",
                    f"Muc: {heading}",
                    f"Trang: {chunk.page_start}-{chunk.page_end}",
                    "Noi dung:",
                    chunk.content,
                ]
            )
        )
    return "\n\n".join(blocks)


async def generate_answer(
    session: AsyncSession,
    llm: ChatNVIDIA,
    query: str,
    chunks: list[RetrievedChunk],
) -> tuple[str, list[Citation]]:
    version_keys = list(dict.fromkeys(chunk.version_key for chunk in chunks))
    version_by_key = await resolve_version_refs(session, version_keys)
    citations = build_citations(chunks, version_by_key)

    context_block = build_context_block(chunks)
    chain = RAG_ANSWER_PROMPT | llm | StrOutputParser()
    answer = await chain.ainvoke({"context": context_block, "question": query})

    return answer, citations
```

---

## 5. `app/api/rag.py` (File Moi)

Theo dung convention da chot o guide 01/06: `APIRouter(tags=[...])` **khong** tu
khai bao `prefix="/api/v1"`, dat truc tiep trong `app/api/` (khong dat trong
`app/api/routes/` - thu muc nay van dang rong, khong co quy uoc nao dung no).

### 5.1 Dependency Cho LLM Va Qdrant Client

Router can 3 dependency: `AsyncSession` (da co `get_session()`), `QdrantClient`
(da co `get_qdrant_client()`), va `ChatNVIDIA` (moi tao o muc 3). Guide nay
khong tao rieng `app/api/deps.py` (ngoai pham vi - xem muc 9 "Khong Lam Trong File
Nay") - khai bao dependency function truc tiep trong `app/api/rag.py`, vi day la
dependency chi rag router dung, chua co router thu 2 nao can dung chung de bien
thanh module `deps.py` rieng (xem muc 8 "Khong Lam Trong File Nay").

### 5.2 Xu Ly Truong Hop 0 Chunk (Khong Goi LLM)

Yeu cau cot loi cua guide nay: neu `retrieve()` tra ve `[]`, tra cau tra loi co
dinh **ngay**, khong goi `generate_answer()`/LLM:

```python
NO_RESULT_ANSWER = "Toi chua tim thay thong tin phu hop trong tai lieu hien co."
```

### 5.3 File Hoan Chinh

```python
"""
Router POST /api/v1/rag/answer.

Flow: RagAnswerRequest -> retrieve() (app/retrieval/retriever.py, guide 04)
  -> neu 0 chunk: tra NO_RESULT_ANSWER ngay, khong goi LLM
  -> generate_answer() (app/llm/rag_chain.py) -> RagAnswerResponse.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.llm.generator import get_chat_llm
from app.llm.rag_chain import generate_answer
from app.retrieval.retriever import retrieve
from app.schemas.rag import RagAnswerRequest, RagAnswerResponse
from app.vectorstore.qdrant_client import get_qdrant_client

router = APIRouter(tags=["rag"])

NO_RESULT_ANSWER = "Toi chua tim thay thong tin phu hop trong tai lieu hien co."


def get_llm() -> ChatNVIDIA:
    """Dependency wrapper cho get_chat_llm(), de test co the override qua
    app.dependency_overrides[get_llm] ma khong goi NVIDIA API thuc."""
    return get_chat_llm()


def get_qdrant() -> QdrantClient:
    """Dependency wrapper cho get_qdrant_client(), cung muc dich override luc test."""
    return get_qdrant_client()


@router.post("/rag/answer", response_model=RagAnswerResponse)
async def answer_rag_query(
    request: RagAnswerRequest,
    session: AsyncSession = Depends(get_session),
    llm: ChatNVIDIA = Depends(get_llm),
    qdrant_client: QdrantClient = Depends(get_qdrant),
) -> RagAnswerResponse:
    """
    POST /api/v1/rag/answer.

    prefer_current hien CHUA duoc dung de loc ket qua (retrieve() - guide 04 -
    khong nhan tham so is_latest/prefer_current). Day la gioi han MVP, giong
    cach guide 04 muc 6 da ghi ro "Gioi Han MVP So Voi Guide 16/18" - khong tu
    y mo rong RetrievalFilter o day.
    """
    trace_id = str(uuid.uuid4())

    chunks = await retrieve(request.query, client=qdrant_client)

    if not chunks:
        return RagAnswerResponse(
            answer=NO_RESULT_ANSWER,
            citations=[],
            related_assets=[],
            trace_id=trace_id,
        )

    answer, citations = await generate_answer(session, llm, request.query, chunks)

    return RagAnswerResponse(
        answer=answer,
        citations=citations,
        related_assets=[],
        trace_id=trace_id,
    )
```

Luu y:

```text
- trace_id dung uuid.uuid4() moi request, khong lay tu header client gui len
  (spec 06_API_SPEC.md khong yeu cau client tu truyen trace_id).
- related_assets luon tra [] trong guide nay - RagAnswerResponse.related_assets
  (guide 03) tai dung AssetMetadata, nhung viec goi document_assets/assets de
  lay asset lien quan la MOT VIEC KHAC (map document -> asset), khong thuoc pham
  vi endpoint tra loi RAG. Neu can, lam o guide rieng, khong tu bo sung query
  moi vao day.
- prefer_current/user_role cua RagAnswerRequest hien CHUA duoc dung de doi hanh
  vi retrieve() - ghi ro trong docstring de nguoi doc sau khong nham la da co
  loc theo is_latest.
- get_llm()/get_qdrant() la wrapper mong quanh get_chat_llm()/get_qdrant_client()
  chi de FastAPI TestClient co the override qua app.dependency_overrides khi
  test (muc 7.2), khong doi logic ben trong 2 ham goc.
```

---

## 6. Wiring Vao `app/main.py`

Sau guide 01/02/06, `main.py` co doan comment placeholder cho rag/documents/
versions/ingestion (xem `01_APP_MAIN_AND_HEALTH_GUIDE.md` muc 5.3). Router `rag`
la router **thu hai** duoc bat that (sau `reference_data` cua guide 06) - uncomment
dung 2 dong cho rag, **khong** uncomment dong cua documents/versions/ingestion (cac
router do van CHUA duoc tao):

```python
from app.api.health import router as health_router
from app.api.reference_data import router as reference_data_router
from app.api.rag import router as rag_router
from app.embedding.embedder import get_embedding

# ... (giu nguyen phan lifespan/FastAPI()/CORSMiddleware da co)

app.include_router(health_router)
app.include_router(reference_data_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")

# from app.api.documents import router as documents_router
# from app.api.versions import router as versions_router
# from app.api.ingestion import router as ingestion_router
#
# app.include_router(documents_router, prefix="/api/v1")
# app.include_router(versions_router, prefix="/api/v1")
# app.include_router(ingestion_router, prefix="/api/v1")
```

---

## 7. Test/Kiem Thu

### 7.1 Unit test `app/llm/rag_chain.py`

File: `chatbot/backend/test/llm/test_rag_chain.py`

Khong goi NVIDIA/Postgres thuc - monkeypatch `session.execute()` bang fake AsyncMock
va dung fake LLM object co method `ainvoke()`.

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.rag_chain import build_citations, build_context_block, generate_answer
from app.retrieval.retriever import RetrievedChunk


def _make_chunk(**overrides) -> RetrievedChunk:
    defaults = dict(
        document_key="qd-3266",
        version_key="qd-3266-2024",
        title="Quy dinh cong tac hoc vu",
        heading_path=["Chuong 1", "Dieu 5"],
        page_start=2,
        page_end=3,
        content="Sinh vien can nop don theo mau...",
        score=0.87,
    )
    defaults.update(overrides)
    return RetrievedChunk(**defaults)


def test_build_context_block_includes_source_markers_and_heading():
    chunks = [_make_chunk()]

    context = build_context_block(chunks)

    assert "[SOURCE 1]" in context
    assert "Chuong 1 > Dieu 5" in context
    assert "Sinh vien can nop don theo mau..." in context


def test_build_citations_skips_chunk_without_matching_version():
    chunks = [_make_chunk(version_key="khong-ton-tai")]

    citations = build_citations(chunks, version_by_key={})

    assert citations == []


def test_build_citations_maps_version_to_document_and_version_id():
    fake_document = MagicMock(title="Quy dinh cong tac hoc vu (Document)")
    fake_version = MagicMock(
        id=34,
        document_id=12,
        title="",
        canonical_markdown_path="qd-3266.md",
        document=fake_document,
    )
    chunks = [_make_chunk()]

    citations = build_citations(chunks, version_by_key={"qd-3266-2024": fake_version})

    assert len(citations) == 1
    citation = citations[0]
    assert citation.document_id == 12
    assert citation.version_id == 34
    assert citation.section_title == "Chuong 1 > Dieu 5"
    assert citation.source_file == "qd-3266.md"


@pytest.mark.asyncio
async def test_generate_answer_calls_llm_and_returns_citations(monkeypatch):
    import app.llm.rag_chain as rag_chain_module

    fake_version = MagicMock(
        id=34,
        document_id=12,
        title="Quy dinh cong tac hoc vu",
        canonical_markdown_path="qd-3266.md",
        document=MagicMock(title="Quy dinh cong tac hoc vu"),
    )

    async def fake_resolve_version_refs(session, version_keys):
        assert version_keys == ["qd-3266-2024"]
        return {"qd-3266-2024": fake_version}

    monkeypatch.setattr(
        rag_chain_module, "resolve_version_refs", fake_resolve_version_refs
    )

    fake_llm = MagicMock()
    fake_chain = AsyncMock()
    fake_chain.ainvoke = AsyncMock(return_value="Ban can nop don theo mau X.")
    monkeypatch.setattr(
        rag_chain_module,
        "RAG_ANSWER_PROMPT",
        MagicMock(__or__=lambda self, other: fake_chain),
    )

    session = AsyncMock()
    chunks = [_make_chunk()]

    answer, citations = await generate_answer(session, fake_llm, "dieu kien?", chunks)

    assert answer == "Ban can nop don theo mau X."
    assert len(citations) == 1
    assert citations[0].version_id == 34
```

Chay:

```bash
cd chatbot/backend
pytest test/llm/test_rag_chain.py -v
```

Ghi chu ve `fake_chain` trong test cuoi: `RAG_ANSWER_PROMPT | llm | StrOutputParser()`
la 3 lan `__or__` lien tiep - test o day don gian hoa bang cach mock hang
`RAG_ANSWER_PROMPT.__or__` de tra thang ve 1 object co `ainvoke()` gia, tranh phai
dung LangChain runtime thuc trong unit test. Neu thay cach nay qua gian lap, co the
thay bang mock `ChatNVIDIA`/`StrOutputParser` that va chi patch method HTTP cua
`ChatNVIDIA`, nhung se phu thuoc sau hon vao noi bo LangChain - chon huong don gian
hoa nay de test on dinh khi upgrade version LangChain.

### 7.2 Test router bang `TestClient` + dependency override

File: `chatbot/backend/test/api/test_rag.py`

```python
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.rag import get_llm, get_qdrant
from app.databases.session import get_session
from app.main import app
from app.retrieval.retriever import RetrievedChunk


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        document_key="qd-3266",
        version_key="qd-3266-2024",
        title="Quy dinh cong tac hoc vu",
        heading_path=["Chuong 1", "Dieu 5"],
        page_start=2,
        page_end=3,
        content="Sinh vien can nop don theo mau...",
        score=0.87,
    )


def test_answer_rag_query_returns_fixed_message_when_no_chunks(monkeypatch):
    import app.api.rag as rag_module

    async def fake_retrieve(query, *, client=None, top_k=None, filters=None):
        return []

    monkeypatch.setattr(rag_module, "retrieve", fake_retrieve)

    app.dependency_overrides[get_session] = lambda: AsyncMock()
    app.dependency_overrides[get_llm] = lambda: AsyncMock()
    app.dependency_overrides[get_qdrant] = lambda: AsyncMock()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/rag/answer",
            json={"query": "Em muon xin bang diem thi can gi?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == rag_module.NO_RESULT_ANSWER
    assert body["citations"] == []
    assert body["related_assets"] == []
    assert body["trace_id"]


def test_answer_rag_query_rejects_blank_query():
    client = TestClient(app)

    response = client.post("/api/v1/rag/answer", json={"query": "   "})

    assert response.status_code == 422
```

Test co chunk (goi qua `generate_answer()` thuc) can mock sau hon (LLM/DB), nen de
lai cho test tich hop rieng (`test/integration/`, xem cau truc thu muc da co) hoac
kiem thu thu cong bang curl o muc 7.3 - phan unit test o day chi tap trung dam bao
early-return khi 0 chunk va validate input hoat dong dung.

Chay:

```bash
cd chatbot/backend
pytest test/api/test_rag.py -v
```

### 7.3 Kiem thu thu cong bang curl

Sau khi `uvicorn app.main:app --reload --port 8000` da chay (can `NVIDIA_API_KEY`/
`LLM_API_KEY`/`QDRANT_URL` hop le trong `.env`, va collection `ctu_chunks_test` da
co du lieu tu ingestion):

```bash
curl -X POST http://localhost:8000/api/v1/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Em muon xin bang diem thi can gi?",
    "user_role": "student",
    "prefer_current": true
  }'
```

Response mong doi khi co ket qua retrieval:

```json
{
  "answer": "Ban can nop don xin cap bang diem theo mau quy dinh tai Phong Cong tac sinh vien...",
  "citations": [
    {
      "document_id": 12,
      "version_id": 34,
      "title": "Quy dinh cong tac hoc vu",
      "page_start": 2,
      "page_end": 3,
      "section_title": "Chuong 1 > Dieu 5",
      "source_file": "qd-3266.md",
      "quote_snippet": "Sinh vien can nop don theo mau..."
    }
  ],
  "related_assets": [],
  "trace_id": "3f1c9e2a-..."
}
```

Response khi collection Qdrant rong hoac cau hoi khong khop chunk nao:

```json
{
  "answer": "Toi chua tim thay thong tin phu hop trong tai lieu hien co.",
  "citations": [],
  "related_assets": [],
  "trace_id": "8a2d5f11-..."
}
```

Kiem tra request rong bi tu choi:

```bash
curl -X POST http://localhost:8000/api/v1/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "   "}'
```

Ky vong `422 Unprocessable Entity` (Pydantic validate `query` khong duoc chi chua
khoang trang, theo `RagAnswerRequest.strip_and_validate` cua guide 03).

---

## 8. Khong Lam Trong File Nay

```text
Khong tao app/api/deps.py rieng - dependency get_llm()/get_qdrant() khai bao
  truc tiep trong app/api/rag.py vi chi rag router dung, chua co router thu 2
  can dung chung.
Khong them eligibility filter (review_status=approved/rag_status=published/
  is_latest) vao retrieve() hay vao router nay - day la thieu sot da duoc guide
  04 muc 6 ghi nhan ro, chua co app/retrieval/eligibility.py trong repo, khong
  tu them dieu kien status rieng o day.
Khong dung prefer_current de loc ket qua - retrieve() (guide 04) khong ho tro
  tham so nay, khong tu mo rong RetrievalFilter (app/vectorstore/models.py)
  ngoai pham vi guide nay.
Khong tra ve related_assets thuc (luon []) - can 1 guide rieng de map
  document -> document_assets -> assets.
Khong them auth/JWT.
Khong them citation_validator.py (kiem tra answer text co nhac dung citation
  hay khong) - guide 18 muc 7 co de xuat item nay nhung ngoai pham vi guide nay,
  de lai cho giai doan sau truoc khi public cho sinh vien thuc.
Khong doi RAG_ANSWER_PROMPT (app/llm/prompts.py) - dung nguyen template that
  dang co (.from_template(), bien {context}/{question}).
Khong tao lai FastAPI() instance moi trong main.py - chi them 2 dong
  import/include_router cho rag_router canh cac dong da co cua guide 01/02/06.
```

---

## 9. Done Khi

- [ ] `app/llm/generator.py` co `get_chat_llm()`, doc `get_api_settings().llm`,
  raise `ValueError` ro rang khi thieu `LLM_API_KEY` hoac provider khac `"nvidia"`.
- [ ] `app/llm/rag_chain.py` co `resolve_version_refs()`, `build_citations()`,
  `build_context_block()`, `generate_answer()`.
- [ ] `build_context_block()` tra ve 1 string (khong phai list message), khop
  dung bien `{context}` cua `RAG_ANSWER_PROMPT` that (`.from_template()`).
- [ ] `build_citations()` bo qua (khong raise loi) chunk co `version_key` khong
  resolve duoc trong Postgres.
- [ ] `generate_answer()` KHONG tu goi `retrieve()` - chi nhan `chunks` co san,
  router chiu trach nhiem goi `retrieve()` truoc.
- [ ] `app/api/rag.py` ton tai, `router = APIRouter(tags=["rag"])`, **khong**
  tu khai bao `prefix="/api/v1"`.
- [ ] `POST /rag/answer` (sau khi include voi prefix o `main.py` la
  `/api/v1/rag/answer`) nhan `RagAnswerRequest`, tra `RagAnswerResponse`.
- [ ] Khi `retrieve()` tra `[]`: response co `answer == NO_RESULT_ANSWER`,
  `citations == []`, và **khong** goi `generate_answer()`/LLM (kiem tra bang
  test `test_answer_rag_query_returns_fixed_message_when_no_chunks`, khong chi
  doc code bang mat).
- [ ] `app/main.py` co them dung 2 dong (`import` + `include_router`) cho
  `rag_router` voi `prefix="/api/v1"`, khong dong toi dong cua
  documents/versions/ingestion (van la comment).
- [ ] `test/llm/test_rag_chain.py` va `test/api/test_rag.py` chay pass voi
  `pytest`, khong can NVIDIA API/Postgres/Qdrant thuc.
- [ ] Curl POST `/api/v1/rag/answer` voi query hop le tra `200` dung shape
  `RagAnswerResponse`; query rong/chi khoang trang tra `422`.
- [ ] Khong co field nao trong response vuot ra ngoai 4 field da chot cua
  `RagAnswerResponse` (guide 03): `answer`, `citations`, `related_assets`,
  `trace_id`.

---

## 10. Phu Thuoc / Thu Tu Lam Truoc

```text
File nay KHONG the viet/chay duoc doc lap - phu thuoc THUC SU vao:

- Guide 03 (03_RAG_ANSWER_SCHEMA_GUIDE.md): can app/schemas/rag.py da duoc
  viet dung theo thiet ke (RagAnswerRequest/Citation/RagAnswerResponse).
  Guide nay import truc tiep tu app.schemas.rag.
- Guide 04 (04_RETRIEVER_IMPLEMENTATION_GUIDE.md): can app/retrieval/retriever.py
  da duoc viet dung theo thiet ke (retrieve()/RetrievedChunk voi 8 field).
  Guide nay import truc tiep tu app.retrieval.retriever.
- Guide 02 (02_SETTINGS_ENV_CORS_GUIDE.md): can app/core/api_settings.py ton tai
  voi get_api_settings().llm (provider/api_key/chat_model) - dung trong
  app/llm/generator.py. Neu Guide 02 chua chot xong huong LLM provider (huong A
  ChatNVIDIA hay huong B ChatOpenAI - xem Guide 02 muc 4), phai chot truoc khi
  viet get_chat_llm() nhu muc 3 o day.
- Guide 01/06 (01_APP_MAIN_AND_HEALTH_GUIDE.md,
  06_REFERENCE_DATA_ENDPOINT_GUIDE.md): can app/main.py da co FastAPI(),
  CORSMiddleware, include_router(health_router),
  include_router(reference_data_router, prefix="/api/v1") - guide nay chi them
  2 dong moi canh do, khong tao lai FastAPI() instance.
- requirements.txt can co fastapi/uvicorn/httpx (Guide 01) va
  langchain-nvidia-ai-endpoints (Guide 02) - hien tai requirements.txt (da doc
  truc tiep) CHUA co ca 2 nhom nay, phai hoan tat Guide 01/02 truoc khi
  `import fastapi`/`import langchain_nvidia_ai_endpoints` trong file nay chay
  duoc.

Cac guide con lai KHONG can lam truoc de viet duoc file nay (documents/versions/
ingestion la nhung endpoint doc lap, khong co dependency 2 chieu voi rag/answer):
- Guide cho documents/versions (08/09/10 trong 00_API_OVERVIEW_AND_CONVENTIONS.md)
  co the lam song song, khong anh huong file nay.
- Guide 20 (E2E_API_SMOKE) se dung lai curl cua muc 7.3 o day trong kich ban
  smoke tong, lam sau khi file nay hoan tat.
```
