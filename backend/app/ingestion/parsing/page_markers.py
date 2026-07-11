from __future__ import annotations

from dataclasses import dataclass
import re

PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.IGNORECASE)

@dataclass(frozen=True)
class PageBlock:
    page_number: int
    content: str
    
# PAGE_NUMBER_LINE_RE = re.compile(r"^\s*\d+\s*$")
# HORIZONTAL_PAGE_RULE_RE = re.compile(r"^\s*---\s*$")

""""
dọn rác OCR nằm sát ranh giới trang, sau khi đã biết chắc nội dung này thuộc page nào.
review.
"""
# def strip_page_boundary_artifacts(
#     text: str,
#     *,
#     current_page_number: int,
#     next_page_number: int | None,
# ) -> str:
#     """Remove only artifacts that can be tied to an explicit page boundary."""
#     lines = text.splitlines()

#     while lines and not lines[0].strip():
#         lines.pop(0)

#     # OCR may repeat the current page number immediately after its marker.
#     if lines and lines[0].strip() == str(current_page_number):
#         lines.pop(0)
#         while lines and not lines[0].strip():
#             lines.pop(0)

#     while lines and not lines[-1].strip():
#         lines.pop()

#     # OCR commonly emits "---" and the next page number immediately before
#     # the next explicit marker. Remove only this verified boundary suffix.
#     if next_page_number is not None and lines and lines[-1].strip() == str(next_page_number):
#         lines.pop()
#         while lines and not lines[-1].strip():
#             lines.pop()
#     if next_page_number is not None and lines and HORIZONTAL_PAGE_RULE_RE.fullmatch(lines[-1]):
#         lines.pop()

#     return "\n".join(lines).strip()


def extract_page_numbers(text: str) -> list[int]:
    return [int(match.group(1)) for match in PAGE_RE.finditer(text)]

def split_body_by_page_markers(body: str) -> list[PageBlock]:
    matches = list(PAGE_RE.finditer(body))
    if not matches:
        raise ValueError("Markdown body requires page marker before chunking")

    blocks: list[PageBlock] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        content_start = match.end()
        content_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(body)
        )
        next_page_number = (
            int(matches[index + 1].group(1))
            if index + 1 < len(matches)
            else None
        )
        # content = strip_page_boundary_artifacts(
        #     body[content_start:content_end],
        #     current_page_number=page_number,
        #     next_page_number=next_page_number,
        # )
        content = body[content_start:content_end].strip() #Lấy toàn bộ nội dung nằm giữa hai page marker. -> xoa khoang trang
        if content:
            blocks.append(PageBlock(page_number=page_number, content=content))

    return blocks

# def extract_page_range(text: str) -> tuple[int | None, int | None]:
#     page_numbers = extract_page_numbers(text)
#     return (min(page_numbers), max(page_numbers)) if page_numbers else (None, None)

# def require_page_range(text: str, *, fallback: tuple[int, int] | None = None) -> tuple[int, int]:
#     page_start, page_end = extract_page_range(text)
    
#     if page_start is not None and page_end is not None:
#         return (page_start, page_end)
#     if fallback is not None:
#         return fallback
#     raise ValueError("Chunk content requires page marker before chunking")


