# Task 05: Chat API (RAG Core)

## Mục tiêu
API chính của chatbot - nhận câu hỏi từ user, tìm kiếm documents liên quan trong Qdrant, và tạo câu trả lời với LLM.

## Endpoint cần implement

### POST /api/v1/chat
```json
Request:
{
  "message": "Quy trình xin nghỉ học tạm thời như thế nào?",
  "conversation_id": "uuid-optional",  // để tiếp tục conversation
  "filters": {                          // optional
    "department_id": 1,
    "document_type_id": 2
  }
}

Response 200:
{
  "answer": "Để xin nghỉ học tạm thời, sinh viên cần thực hiện các bước sau:\n1. Điền đơn xin nghỉ...",
  "conversation_id": "uuid",
  "sources": [
    {
      "document_id": 1,
      "document_version_id": 5,
      "title": "Quy định về nghỉ học tạm thời",
      "chunk_key": "qd-123-chunk-2",
      "relevance_score": 0.89,
      "snippet": "...sinh viên có thể xin nghỉ học tạm thời không quá 2 học kỳ..."
    }
  ],
  "metadata": {
    "retrieval_time_ms": 45,
    "generation_time_ms": 1200,
    "chunks_retrieved": 5,
    "model": "gpt-4"
  }
}

Response 400: { "detail": "Message cannot be empty" }
Response 503: { "detail": "LLM service unavailable" }
```

---

## Architecture

```
User Message
     │
     ▼
┌─────────────┐
│  Embedding  │  ← Tạo vector từ user message
└─────────────┘
     │
     ▼
┌─────────────┐
│   Qdrant    │  ← Tìm k chunks gần nhất (cosine similarity)
│   Search    │     Filter: rag_status=published
└─────────────┘
     │
     ▼
┌─────────────┐
│  Retrieve   │  ← Lấy full content từ parent chunks
│  Parents    │
└─────────────┘
     │
     ▼
┌─────────────┐
│    LLM      │  ← Generate answer với context
│  Generate   │
└─────────────┘
     │
     ▼
  Response
```

---

## Checklist

### Backend - Schemas

- [ ] **Tạo file** `backend/app/schemas/chat.py`
```python
from __future__ import annotations
from typing import Optional
from pydantic import Field
from app.schemas.base import StrictSchema


class ChatRequest(StrictSchema):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    filters: ChatFilters | None = None


class ChatFilters(StrictSchema):
    department_id: int | None = None
    document_type_id: int | None = None
    domain: str | None = None


class SourceDocument(StrictSchema):
    document_id: int
    document_version_id: int
    title: str
    chunk_key: str
    relevance_score: float
    snippet: str


class ChatMetadata(StrictSchema):
    retrieval_time_ms: int
    generation_time_ms: int
    chunks_retrieved: int
    model: str


class ChatResponse(StrictSchema):
    answer: str
    conversation_id: str
    sources: list[SourceDocument]
    metadata: ChatMetadata
```

### Backend - Retriever

- [ ] **Update retriever** `backend/app/retrieval/retriever.py`
```python
import time
from qdrant_client.models import Filter, FieldCondition, MatchValue

async def retrieve_relevant_chunks(
    query_embedding: list[float],
    top_k: int = 5,
    filters: dict | None = None,
) -> list[dict]:
    """Search Qdrant for relevant chunks."""
    
    start = time.perf_counter()
    
    # Build filter - only published documents
    must_conditions = [
        FieldCondition(
            key="rag_status",
            match=MatchValue(value="published")
        )
    ]
    
    # Add optional filters
    if filters:
        if filters.get("department_id"):
            must_conditions.append(
                FieldCondition(
                    key="department_id",
                    match=MatchValue(value=filters["department_id"])
                )
            )
        if filters.get("document_type_id"):
            must_conditions.append(
                FieldCondition(
                    key="document_type_id",
                    match=MatchValue(value=filters["document_type_id"])
                )
            )
    
    search_filter = Filter(must=must_conditions)
    
    # Search Qdrant
    client = get_qdrant_client()
    results = client.search(
        collection_name="chunks",
        query_vector=query_embedding,
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )
    
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    
    return {
        "chunks": [
            {
                "chunk_key": hit.payload["chunk_key"],
                "document_id": hit.payload["document_id"],
                "document_version_id": hit.payload["document_version_id"],
                "title": hit.payload.get("title", ""),
                "content": hit.payload.get("content", ""),
                "score": hit.score,
            }
            for hit in results
        ],
        "retrieval_time_ms": elapsed_ms,
    }
```

### Backend - Chat Service

- [ ] **Tạo file** `backend/app/chat/service.py`
```python
import time
import uuid
from app.embedding.embedder import get_embeddings
from app.retrieval.retriever import retrieve_relevant_chunks
from app.llm.rag_chain import generate_answer


async def process_chat(
    message: str,
    conversation_id: str | None = None,
    filters: dict | None = None,
) -> dict:
    """Process a chat message and return answer with sources."""
    
    # Generate conversation ID if not provided
    conv_id = conversation_id or str(uuid.uuid4())
    
    # 1. Embed the user message
    query_embedding = await get_embeddings([message])
    query_vector = query_embedding[0]
    
    # 2. Retrieve relevant chunks
    retrieval_result = await retrieve_relevant_chunks(
        query_embedding=query_vector,
        top_k=5,
        filters=filters,
    )
    
    chunks = retrieval_result["chunks"]
    retrieval_time = retrieval_result["retrieval_time_ms"]
    
    # 3. Build context from chunks
    context = "\n\n---\n\n".join([
        f"[{c['title']}]\n{c['content']}"
        for c in chunks
    ])
    
    # 4. Generate answer with LLM
    gen_start = time.perf_counter()
    answer = await generate_answer(
        question=message,
        context=context,
    )
    gen_time = int((time.perf_counter() - gen_start) * 1000)
    
    # 5. Build response
    return {
        "answer": answer,
        "conversation_id": conv_id,
        "sources": [
            {
                "document_id": c["document_id"],
                "document_version_id": c["document_version_id"],
                "title": c["title"],
                "chunk_key": c["chunk_key"],
                "relevance_score": round(c["score"], 3),
                "snippet": c["content"][:200] + "..." if len(c["content"]) > 200 else c["content"],
            }
            for c in chunks
        ],
        "metadata": {
            "retrieval_time_ms": retrieval_time,
            "generation_time_ms": gen_time,
            "chunks_retrieved": len(chunks),
            "model": "gpt-4",  # or from config
        },
    }
```

### Backend - Endpoint

- [ ] **Tạo file** `backend/app/api/chat.py`
```python
from fastapi import APIRouter, HTTPException

from app.chat.service import process_chat
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await process_chat(
            message=request.message,
            conversation_id=request.conversation_id,
            filters=request.filters.model_dump() if request.filters else None,
        )
        return ChatResponse(**result)
    
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    
    except Exception as exc:
        # Log the error
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        ) from exc
```

- [ ] **Đăng ký router** trong `backend/app/main.py`
```python
from app.api.chat import router as chat_router

app.include_router(chat_router, prefix="/api/v1")
```

### Backend - LLM Integration

- [ ] **Update hoặc tạo** `backend/app/llm/rag_chain.py`
```python
from app.llm.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.llm.generator import get_llm_client


async def generate_answer(question: str, context: str) -> str:
    """Generate answer using LLM with retrieved context."""
    
    client = get_llm_client()
    
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user", "content": RAG_USER_TEMPLATE.format(
            context=context,
            question=question,
        )},
    ]
    
    response = await client.chat.completions.create(
        model="gpt-4",  # or from config
        messages=messages,
        temperature=0.3,
        max_tokens=1000,
    )
    
    return response.choices[0].message.content
```

- [ ] **Thêm prompts** trong `backend/app/llm/prompts.py`
```python
RAG_SYSTEM_PROMPT = """Bạn là trợ lý AI của Trường Đại học Cần Thơ, chuyên hỗ trợ sinh viên về các quy định, quy trình và thủ tục hành chính.

Hướng dẫn:
- Trả lời dựa trên thông tin được cung cấp trong ngữ cảnh
- Nếu thông tin không có trong ngữ cảnh, nói rõ "Tôi không tìm thấy thông tin về vấn đề này trong tài liệu"
- Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu
- Nếu có các bước thực hiện, liệt kê theo thứ tự
- Đề cập nguồn tài liệu khi phù hợp"""

RAG_USER_TEMPLATE = """Ngữ cảnh từ tài liệu:
{context}

Câu hỏi: {question}

Trả lời:"""
```

---

## Test

```bash
# Basic chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quy trình xin nghỉ học tạm thời?"}'

# Chat with filters
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quy định học bổng",
    "filters": {"department_id": 1}
  }'

# Continue conversation
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Cần những giấy tờ gì?",
    "conversation_id": "abc-123"
  }'
```

---

## Performance Considerations

1. **Caching**: Cache embeddings cho các câu hỏi phổ biến
2. **Streaming**: Implement SSE cho real-time response (optional)
3. **Rate limiting**: Giới hạn requests per user
4. **Timeout**: Set timeout cho LLM calls (30s recommended)

---

## Definition of Done

- [ ] Endpoint POST /chat hoạt động end-to-end
- [ ] Trả về answer + sources + metadata
- [ ] Filter chỉ documents published
- [ ] Optional filters (department, document_type) hoạt động
- [ ] Xử lý errors gracefully (400, 503)
- [ ] Response time < 5s cho typical queries
- [ ] Prompts tuned cho domain CTU
