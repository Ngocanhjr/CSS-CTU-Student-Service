# CTU Student Service Backend

FastAPI backend quản lý metadata, ingestion, hybrid retrieval và câu trả lời RAG có citation.

## Trách nhiệm

- Nhận canonical Markdown, metadata, assets và file nguồn tùy chọn.
- Lưu file trên Cloudflare R2.
- Validate và review tài liệu.
- Tạo parent/child chunks; lưu metadata và nội dung chuẩn trong PostgreSQL.
- Tạo embedding child chunks bằng Cloudflare Workers AI và index vào Qdrant.
- Hybrid retrieval, RRF, structural expansion và Jina reranking tùy chọn.
- Sinh câu trả lời grounded qua endpoint OpenAI-compatible.

OCR/LlamaParse nằm ngoài backend này.

## Module

| Module | Trách nhiệm |
| --- | --- |
| `app/api` | HTTP, dependency injection và ánh xạ lỗi |
| `app/ingestion` | Upload, review, parse, chunk và index orchestration |
| `app/documents` | Quản lý document version, assets và lifecycle |
| `app/retrieval` | Eligibility, dense/sparse retrieval, fusion, hydration và context |
| `app/rag` | Điều phối retrieval → LLM → citation |
| `app/llm` | Model và prompt capability |
| `app/embedding` | Cloudflare Workers AI embedding |
| `app/vectorstore` | Qdrant client/repository |
| `app/databases` | SQLAlchemy models, session và repositories |
| `app/schemas` | DTO Pydantic |

## Data contract

- PostgreSQL là nguồn chuẩn cho metadata, quan hệ và chunk content.
- Qdrant lưu vector child chunks và structural payload, không phải canonical content.
- Student retrieval yêu cầu `review_status=approved`, `rag_status=published` và audience phù hợp.
- Hydration kiểm tra lại eligibility từ PostgreSQL trước khi đưa hit vào câu trả lời.

## Cấu hình runtime

Biến môi trường mẫu nằm ở `../.env.example`. Các giá trị chunking/retrieval không nhạy cảm nằm trong `app/config/runtime.yaml`.

Jina reranker là tùy chọn:

```dotenv
JINA_API_KEY=
JINA_RERANK_MODEL=jina-reranker-v3
JINA_RERANK_URL=https://api.jina.ai/v1/rerank
JINA_RERANK_TIMEOUT=8
```

Query rewriting mặc định được bật:

```dotenv
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_MAX_QUERIES=3
QUERY_REWRITE_TIMEOUT_SECONDS=12
```

## Chạy backend

```powershell
python -m pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

- Health: `GET /health`
- Database health: `GET /api/v1/health/database`
- OpenAPI: `GET /docs`
- RAG answer: `POST /api/v1/rag/answer`

Xem hướng dẫn đầy đủ tại `../SETUP.md`.
