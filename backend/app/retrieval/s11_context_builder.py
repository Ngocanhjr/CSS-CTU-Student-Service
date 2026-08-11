# Ghép parent context trước child chunks.
# Cùng một parent chỉ xuất hiện một lần.
# Ưu tiên giữ nội dung child nếu parent quá dài.
# Giới hạn context mặc định 12.000 ký tự trước khi gửi LLM.

"""Build bounded LLM context from hydrated retrieval results."""

from app.retrieval.models import RetrievalResult


def _truncate_text(text: str, max_length: int) -> str:
    """Cắt nội dung nhưng không vượt quá giới hạn."""

    if max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    if max_length == 1:
        return "…"

    return f"{text[: max_length - 1].rstrip()}…"


def build_retrieval_context(
    results: list[RetrievalResult],
    *,
    max_characters: int = 12_000,
) -> str:
    """Ghép parent trước child và giới hạn kích thước context."""

    if max_characters <= 0:
        return ""

    sections: list[str] = []
    included_parent_keys: set[str] = set()
    included_chunk_keys: set[str] = set()
    current_length = 0

    def append_section(section: str) -> bool:
        nonlocal current_length

        section = section.strip()
        if not section:
            return False

        separator_length = 2 if sections else 0
        required_length = separator_length + len(section)

        if current_length + required_length > max_characters:
            return False

        sections.append(section)
        current_length += required_length
        return True

    for result in results:
        if result.chunk_key in included_chunk_keys:
            continue

        child_content = result.content.strip()
        if not child_content:
            continue

        child_section = (
            f"[Nguồn | {result.title} | {result.citation}]\n"
            f"{child_content}"
        )

        parent_key = result.parent_chunk_key
        should_add_parent = (
            parent_key is not None
            and result.parent_content is not None
            and result.parent_content.strip() != ""
            and parent_key not in included_parent_keys
        )

        if should_add_parent:
            parent_section = (
                f"[Ngữ cảnh cha | {result.title} | "
                f"{result.citation}]\n"
                f"{result.parent_content.strip()}"
            )

            separator_before_parent = 2 if sections else 0
            separator_before_child = 2

            pair_length = (
                separator_before_parent
                + len(parent_section)
                + separator_before_child
                + len(child_section)
            )

            # Cả parent và child đều còn đủ chỗ.
            if current_length + pair_length <= max_characters:
                append_section(parent_section)
                included_parent_keys.add(parent_key)

                append_section(child_section)
                included_chunk_keys.add(result.chunk_key)
                continue

            # Parent quá dài nhưng child vẫn vừa:
            # cắt parent và dành chỗ cho child.
            child_separator = 2 if sections else 0
            child_required = child_separator + len(child_section)

            if current_length + child_required <= max_characters:
                available_for_parent = (
                    max_characters
                    - current_length
                    - separator_before_parent
                    - separator_before_child
                    - len(child_section)
                )

                if available_for_parent >= 100:
                    truncated_parent = _truncate_text(
                        parent_section,
                        available_for_parent,
                    )

                    if append_section(truncated_parent):
                        included_parent_keys.add(parent_key)

                append_section(child_section)
                included_chunk_keys.add(result.chunk_key)
                continue

        # Không có parent hoặc parent không thể thêm.
        if append_section(child_section):
            included_chunk_keys.add(result.chunk_key)
            continue

        # Child đầu tiên quá dài thì vẫn lấy phần nội dung vừa giới hạn.
        separator_length = 2 if sections else 0
        available_length = (
            max_characters
            - current_length
            - separator_length
        )

        if available_length > 0:
            truncated_child = _truncate_text(
                child_section,
                available_length,
            )

            if append_section(truncated_child):
                included_chunk_keys.add(result.chunk_key)

        break

    return "\n\n".join(sections)