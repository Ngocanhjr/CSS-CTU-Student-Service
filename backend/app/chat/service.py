"""Chat service - orchestrates retrieval and generation."""

import time
import uuid

from app.retrieval.retriever import retrieve_relevant_chunks
from app.llm.rag_chain import generate_answer
from app.schemas.chat import ChatFilters


async def process_chat(
    message: str,
    conversation_id: str | None = None,
    filters: ChatFilters | None = None,
) -> dict:
    """
    Process a chat message and return answer with sources.

    Args:
        message: User's question
        conversation_id: Optional ID to continue a conversation
        filters: Optional filters for retrieval

    Returns:
        dict with answer, sources, conversation_id, and metadata
    """
    # Generate conversation ID if not provided
    conv_id = conversation_id or str(uuid.uuid4())

    # 1. Retrieve relevant chunks (retriever handles embedding internally)
    filter_dict = filters.model_dump(exclude_none=True) if filters else None
    retrieval_result = retrieve_relevant_chunks(
        query=message,
        top_k=5,
        filters=filter_dict,
    )

    chunks = retrieval_result["chunks"]
    retrieval_time = retrieval_result["retrieval_time_ms"]

    # 2. Build context from chunks
    if chunks:
        context = "\n\n---\n\n".join([
            f"[{c['title']}]\n{c['content']}"
            for c in chunks
        ])
    else:
        context = ""

    # 3. Generate answer with LLM
    gen_start = time.perf_counter()
    answer, model_name = await generate_answer(
        question=message,
        context=context,
    )
    gen_time = int((time.perf_counter() - gen_start) * 1000)

    # 4. Build response with sources matching schema
    return {
        "answer": answer,
        "conversation_id": conv_id,
        "sources": [
            {
                "document_key": c["document_key"],
                "version_key": c["version_key"],
                "title": c["title"],
                "chunk_key": c["chunk_key"],
                "relevance_score": round(c["score"], 3),
                "snippet": c["content"][:200] + "..." if len(c["content"]) > 200 else c["content"],
                "heading_path": c.get("heading_path", []),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
            }
            for c in chunks
        ],
        "metadata": {
            "retrieval_time_ms": retrieval_time,
            "generation_time_ms": gen_time,
            "chunks_retrieved": len(chunks),
            "model": model_name,
        },
    }
