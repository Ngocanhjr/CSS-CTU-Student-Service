# Đọc file markdown và tách phần frontmatter YAML khỏi nội dung chính.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.schemas.documents import DocumentMetadata

@dataclass(frozen=True)
class MarkdownDocument:
    path: Path # đường dẫn file gốc
    metadata: DocumentMetadata #metadata
    body: str #nội dung file
    raw_frontmatter: dict[str, Any] #giữ lại yaml gốc

def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")

    if not normalized.startswith("---\n"):
        raise ValueError("Markdown file must start with YAML frontmatter")

    closing_marker = "\n---\n"
    closing_index = normalized.find(closing_marker, len("---\n"))
    if closing_index == -1:
        raise ValueError("Markdown file has no closing YAML frontmatter marker")

    yaml_text = normalized[len("---\n"):closing_index]
    body = normalized[closing_index + len(closing_marker):]

    frontmatter = yaml.safe_load(yaml_text) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    if not body.strip():
        raise ValueError("Markdown body is empty")

    return frontmatter, body.strip()

def read_markdown_document(path: str | Path) -> MarkdownDocument:
    markdown_path = Path(path)
    text = markdown_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    metadata = DocumentMetadata(**frontmatter)

    return MarkdownDocument(
        path=markdown_path,
        metadata=metadata,
        body=body,
        raw_frontmatter=frontmatter,
    )
    
def render_markdown_document(
    metadata: DocumentMetadata,
    body: str,
) -> str:
    yaml_text = yaml.safe_dump(
        metadata.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
    )

    return f"---\n{yaml_text}---\n\n{body.strip()}\n"
