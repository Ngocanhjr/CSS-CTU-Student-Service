from __future__ import annotations

import re

PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.IGNORECASE)

def extract_page_numbers(text: str) -> list[int]:
    return [int(match.group(1)) for match in PAGE_RE.finditer(text)]

def extract_page_range(text: str) -> tuple[int | None, int | None]:
    page_numbers = extract_page_numbers(text)
    return (min(page_numbers), max(page_numbers)) if page_numbers else (None, None)

def require_page_range(text: str, *, fallback: tuple[int, int] | None = None) -> tuple[int, int]:
    page_start, page_end = extract_page_range(text)
    
    if page_start is not None and page_end is not None:
        return (page_start, page_end)
    if fallback is not None:
        return fallback
    raise