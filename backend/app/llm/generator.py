"""NVIDIA chat-model configuration for grounded RAG answers."""

from langchain_nvidia_ai_endpoints import ChatNVIDIA


def get_chat_model() -> ChatNVIDIA:
    return ChatNVIDIA(
        model="qwen/qwen3-next-80b-a3b-instruct",
        temperature=0.1,
        top_p=0.7,
        max_completion_tokens=1024,
    )
