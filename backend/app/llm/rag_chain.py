"""RAG chain for generating answers with retrieved context.

Functions:
    generate_answer: Generate answer using LLM with retrieved context.
"""

import os

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.llm.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE


def get_llm_client() -> ChatNVIDIA:
    """Get NVIDIA LLM client."""
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct")

    if not api_key:
        raise ValueError("NVIDIA_API_KEY chưa được cấu hình.")

    return ChatNVIDIA(
        model=model,
        api_key=api_key,
        temperature=0.3,
        max_tokens=1000,
    )


async def generate_answer(question: str, context: str) -> tuple[str, str]:
    """Generate answer using LLM with retrieved context.

    Args:
        question: The user's question.
        context: Retrieved context from documents.

    Returns:
        Tuple of (answer string, model name).
    """
    model = os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct")
    client = get_llm_client()

    messages = [
        ("system", RAG_SYSTEM_PROMPT),
        ("human", RAG_USER_TEMPLATE.format(
            context=context,
            question=question,
        )),
    ]

    response = await client.ainvoke(messages)

    return response.content, model
