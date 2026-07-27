"""Chat API endpoint."""

from fastapi import APIRouter, HTTPException

from app.chat.service import process_chat
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message and return AI-generated answer.

    - Embeds the user message
    - Retrieves relevant chunks from Qdrant
    - Generates answer using LLM with retrieved context
    - Returns answer with sources and metadata
    """
    try:
        result = await process_chat(
            message=request.message,
            conversation_id=request.conversation_id,
            filters=request.filters,
        )
        return ChatResponse(**result)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        # Log the error in production
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        ) from exc
