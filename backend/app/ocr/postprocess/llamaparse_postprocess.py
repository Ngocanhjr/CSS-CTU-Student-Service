from __future__ import annotations

"""Giữ hierarchy agentic; riêng biểu mẫu dùng chuẩn hóa chuyên biệt."""

from collections import Counter
import re

try:
    from .form_postprocess import normalize_form_document_lines
    from .table_postprocess import (
        convert_html_tables_to_markdown,
        fix_html_table_page_continuations,
        normalize_tables,
    )
except ModuleNotFoundError:  # Cho phép chạy trực tiếp file này.
    from form_postprocess import normalize_form_document_lines
    from table_postprocess import (
        convert_html_tables_to_markdown,
        fix_html_table_page_continuations,
        normalize_tables,
    )


def split_yaml_frontmatter(markdown: str) -> tuple[str, str]:
    """Tách YAML front matter để hậu xử lý không sửa metadata."""

    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", markdown

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[: index + 1]), "".join(lines[index + 1 :])

    return "", markdown


def collapse_excess_blank_lines(markdown: str) -> str:
    """Gộp nhiều hơn hai dòng trắng liên tiếp."""

    return re.sub(r"\n{4,}", "\n\n\n", markdown).strip() + "\n"


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*)\.\s+.+$")
ARTICLE_RE = re.compile(r"^Điều\s+\d+\.\s*.*$", flags=re.IGNORECASE)
VISUAL_CAPTION_RE = re.compile(r"^seal and signature of\s+(.+)$", flags=re.IGNORECASE)
BOLD_HEADING_RE = re.compile(r"^\*\*(#{1,6}\s+.+?)\*\*$")
ESCAPED_BULLET_RE = re.compile(r"^(\s*)\\+([-+*])(?=\s)")
ESCAPED_ORDERED_RE = re.compile(r"^(\s*\d+)\\+\.(?=\s)")


def normalize_structure(markdown: str) -> str:
    """Sửa hierarchy bằng sibling family, không hard-code level theo cú pháp."""

    lines = markdown.splitlines()
    families: dict[tuple[object, ...], list[tuple[int, int]]] = {}
    missing: dict[tuple[object, ...], list[int]] = {}
    numbered_nodes: set[tuple[int, tuple[int, ...]]] = set()
    depth_levels: dict[tuple[int, int], list[int]] = {}
    seen_h1: set[str] = set()
    group = 0
    in_fence = False

    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = HEADING_RE.match(line)
        content = heading.group(2) if heading else line
        numbered = NUMBERED_RE.match(content)
        article = ARTICLE_RE.match(content)

        if heading and len(heading.group(1)) == 1 and not numbered:
            key = re.sub(r"[:\s]+", " ", content).strip().casefold()
            if key in seen_h1:
                lines[index] = f"**{content.strip('*_ ')}**"
                continue
            seen_h1.add(key)
            group += 1

        family: tuple[object, ...] | None = None
        if numbered:
            parts = tuple(int(part) for part in numbered.group(1).split("."))
            family = (group, "number", parts[:-1])
            if heading:
                numbered_nodes.add((group, parts))
                depth_levels.setdefault((group, len(parts)), []).append(len(heading.group(1)))
        elif article:
            family = (group, "article")

        if family and heading:
            families.setdefault(family, []).append((index, len(heading.group(1))))
        elif family and (article or len(parts) > 1):
            missing.setdefault(family, []).append(index)

    for family, headings in families.items():
        canonical = Counter(level for _, level in headings).most_common(1)[0][0]
        for index, old_level in headings:
            lines[index] = "#" * canonical + lines[index][old_level:]
        if len(headings) >= 2:
            for index in missing.get(family, []):
                lines[index] = f"{'#' * canonical} {lines[index]}"

    # Một nhánh mới vẫn dùng level đã được thiết lập ở cùng độ sâu số mục.
    for (group_id, kind, parent), indices in missing.items():
        if (
            kind != "number"
            or len(indices) < 2
            or (group_id, parent) not in numbered_nodes
        ):
            continue
        levels = depth_levels.get((group_id, len(parent) + 1), [])
        if not levels:
            continue
        canonical = Counter(levels).most_common(1)[0][0]
        for index in indices:
            if not HEADING_RE.match(lines[index]):
                lines[index] = f"{'#' * canonical} {lines[index]}"

    return "\n".join(lines)


def normalize_markdown_lines(markdown: str) -> str:
    """Sửa syntax bị escape và xóa formatting rỗng, trừ code fence."""

    out: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            heading = BOLD_HEADING_RE.match(line)
            if heading:
                line = heading.group(1)
            line = ESCAPED_BULLET_RE.sub(r"\1\2", line)
            line = ESCAPED_ORDERED_RE.sub(r"\1.", line)
            caption = VISUAL_CAPTION_RE.match(line)
            if caption:
                line = f"**{caption.group(1).strip()}**"
            compact = line.strip().replace(" ", "")
            if "\\" in compact and set(compact) <= {"*", "\\"}:
                continue
        out.append(line)
    return "\n".join(out)


def postprocess_llamaparse_markdown(markdown: str) -> str:
    """Giữ heading chung; form được phép sửa title/quốc hiệu/Kính gửi."""

    frontmatter, body = split_yaml_frontmatter(markdown)
    body = normalize_markdown_lines(body)
    body = normalize_form_document_lines(body)
    body = normalize_structure(body)
    body = fix_html_table_page_continuations(body)
    body = convert_html_tables_to_markdown(body)
    body = normalize_tables(body)
    body = collapse_excess_blank_lines(body)

    if frontmatter:
        return frontmatter.rstrip() + "\n\n" + body
    return body
