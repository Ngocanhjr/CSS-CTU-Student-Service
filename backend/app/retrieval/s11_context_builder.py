# ghép parent context trước child chunks;
# cùng một parent chỉ xuất hiện một lần;
# giới hạn context mặc định 12.000 ký tự trước khi gửi LLM.

"""Build bounded LLM context from hydrated retrieval results."""

from app.retrieval.models import RetrievalResult


def build_retrieval_context(
    results: list[RetrievalResult],
    *,
    max_characters: int = 12_000,
) -> str:
    """Include each parent once, followed by its relevant child chunks."""
    sections: list[str] = []
    included_parent_keys: set[str] = set()
    included_chunk_keys: set[str] = set()
    current_length = 0

    for result in results:
        if result.chunk_key in included_chunk_keys:
            continue

        parent_key = result.parent_chunk_key
        if (
            parent_key
            and result.parent_content
            and parent_key not in included_parent_keys
        ):
            parent_section = (
                f"[Parent context | {result.title} | {result.citation}]\n"
                f"{result.parent_content.strip()}"
            )
            if current_length + len(parent_section) > max_characters:
                break
            sections.append(parent_section)
            current_length += len(parent_section)
            included_parent_keys.add(parent_key)

        child_section = (
            f"[Source | {result.title} | {result.citation}]\n"
            f"{result.content.strip()}"
        )
        if current_length + len(child_section) > max_characters:
            break

        sections.append(child_section)
        current_length += len(child_section)
        included_chunk_keys.add(result.chunk_key)

    return "\n\n".join(sections)
