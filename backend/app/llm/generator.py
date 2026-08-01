"""Chat-model configuration for grounded RAG answers.

Provider-agnostic: dùng endpoint OpenAI-compatible nên có thể đổi provider
(OpenRouter, Groq, Together, DashScope, vLLM/Ollama local...) chỉ bằng cách
sửa các biến trong .env, không cần sửa code.

Biến môi trường:
    LLM_BASE_URL   URL endpoint OpenAI-compatible (mặc định: OpenRouter).
    LLM_API_KEY    API key của provider.
    LLM_MODEL      Tên model chính xác theo provider (giữ họ Qwen).
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3-next-80b-a3b-instruct"
DEFAULT_TIMEOUT_SECONDS = 45.0


def get_chat_model(
    *,
    max_tokens: int = 1024,
    timeout_seconds: float | None = None,
) -> ChatOpenAI:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY chưa được cấu hình.")

    if timeout_seconds is None:
        timeout_seconds = float(
            os.getenv("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        )

    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        temperature=0.1,
        top_p=0.7,
        max_tokens=max_tokens,
        request_timeout=timeout_seconds,
        max_retries=0,
    )
