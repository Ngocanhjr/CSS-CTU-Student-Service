from __future__ import annotations

import hashlib
import json
import re
import sys
import types
import uuid
from datetime import date, datetime
from pathlib import Path

import yaml


DEFAULT_SOURCE = Path(
    r"E:\RHNA\1Visual\NLCS\Dataset\06_Processing\01_OCR_Output\PDFs_CTSV"
    r"\QuyetDinh\QD3266_Quy_dinh_cong_tac_hoc_vu_danh_cho_sinh_vien_"
    r"trinh_do_dai_hoc_hinh_thuc_chinh_quy_V3_llp.md"
)
OUTPUT = Path(__file__).parent / "fixtures" / "qd3266_retrieval_fixture.json"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


def _load_parser():
    """Load the pure parser without importing FastAPI/Pydantic package initializers."""
    app_root = Path(__file__).parents[2]
    app = types.ModuleType("app")
    app.__path__ = [str(app_root)]
    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = [str(app_root / "schemas")]
    enums = types.ModuleType("app.schemas.enums")
    enums.BlockType = str
    enums.Severity = str
    sys.modules.update(
        {
            "app": app,
            "app.schemas": schemas,
            "app.schemas.enums": enums,
        }
    )

    from app.ingestion.parsing.page_markers import (  # noqa: PLC0415
        PageBlock,
        split_body_by_page_markers,
    )
    from app.ingestion.parsing.structural_parser import parse_page_blocks  # noqa: PLC0415

    return PageBlock, split_body_by_page_markers, parse_page_blocks


def _read_source(source: Path):
    PageBlock, split_pages, parse_pages = _load_parser()
    raw_bytes = source.read_bytes()
    raw_text = raw_bytes.decode("utf-8").replace("\r\n", "\n")
    closing = raw_text.find("\n---\n", 4)
    if not raw_text.startswith("---\n") or closing < 0:
        raise ValueError("Invalid YAML frontmatter")

    frontmatter = yaml.safe_load(raw_text[4:closing])
    raw_pages = split_pages(raw_text[closing + 5 :].strip())
    pages = []
    for index, page in enumerate(raw_pages):
        lines = page.content.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if (
            index + 1 < len(raw_pages)
            and lines
            and lines[-1].strip() == str(raw_pages[index + 1].page_number)
        ):
            lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
        if index + 1 < len(raw_pages) and lines and lines[-1].strip() == "---":
            lines.pop()
        content = "\n".join(lines).strip()
        if content:
            pages.append(PageBlock(page.page_number, content))

    return raw_bytes, frontmatter, pages, parse_pages(pages)


def _parent_groups(blocks):
    parents = []
    current = {"heading_path": ["Document"], "blocks": []}
    for block in blocks:
        if block.block_type == "heading":
            if current["blocks"]:
                parents.append(current)
            current = {"heading_path": block.heading_path, "blocks": [block]}
        else:
            current["blocks"].append(block)
    if current["blocks"]:
        parents.append(current)
    return parents


def _child_groups(parent):
    groups = []
    by_item_path = {}
    for block in parent["blocks"]:
        if block.block_type == "heading":
            continue
        if block.block_type in {"numbered_item", "lettered_item", "bullet_item"}:
            group = {"root": block, "blocks": [block]}
            groups.append(group)
            by_item_path[tuple(block.item_path)] = group
        elif (
            block.block_type == "paragraph"
            and block.item_path
            and tuple(block.item_path) in by_item_path
        ):
            by_item_path[tuple(block.item_path)]["blocks"].append(block)
        else:
            groups.append({"root": block, "blocks": [block]})
    return groups


def _split_oversized(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    parts = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            floor = start + CHUNK_SIZE // 2
            cut = max(
                text.rfind("\n\n", floor, end),
                text.rfind(". ", floor, end),
                text.rfind("; ", floor, end),
                text.rfind(" ", floor, end),
            )
            if cut > floor:
                end = cut + 1
        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return parts


def _iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _embedding_text(frontmatter, root, heading_path, content, page_start, page_end):
    lines = [
        f"Tai lieu: {frontmatter['title']}",
        "Don vi: " + ", ".join(frontmatter["responsible_department"]),
        f"Loai: {frontmatter['document_type']}",
        "Muc: " + " > ".join(heading_path),
    ]
    if root.legal_unit_type != "none":
        lines.append(f"Don vi phap ly: {root.legal_unit_type}")
    ancestors = (
        root.item_path[:-1]
        if root.block_type in {"numbered_item", "lettered_item", "bullet_item"}
        else root.item_path
    )
    if ancestors:
        lines.append("Ngu canh muc cha: " + " > ".join(ancestors))
    lines.append(
        f"Trang: {page_start}-{page_end}"
        if page_start != page_end
        else f"Trang: {page_start}"
    )
    clean_content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
    return "\n".join([*lines, "", clean_content])


def _build_chunk_records(frontmatter, parents, source_file: str):
    document_key = frontmatter["document_key"]
    version_key = frontmatter["version_key"]
    records = []
    child_counter = 1
    chunk_index = 0

    for parent_counter, parent in enumerate(parents, start=1):
        parent_key = f"{version_key}::p::{parent_counter:04d}"
        parent_blocks = parent["blocks"]
        parent_content = "\n\n".join(
            block.raw_content.strip()
            for block in parent_blocks
            if block.raw_content.strip()
        )
        parent_page_start = min(block.page_start for block in parent_blocks)
        parent_page_end = max(block.page_end for block in parent_blocks)
        records.append(
            {
                "postgres": {
                    "chunk_key": parent_key,
                    "parent_chunk_key": None,
                    "chunk_index": chunk_index,
                    "chunk_type": "parent",
                    "heading_path": parent["heading_path"],
                    "section_title": parent["heading_path"][-1],
                    "content": parent_content,
                    "page_start": parent_page_start,
                    "page_end": parent_page_end,
                    "token_count": len(parent_content.split()),
                    "qdrant_point_id": None,
                    "index_status": "not_indexed",
                },
                "structural": {
                    "context_only": not any(
                        block.block_type != "heading" for block in parent_blocks
                    )
                },
                "embedding": None,
                "qdrant": None,
            }
        )
        chunk_index += 1

        for group in _child_groups(parent):
            root = group["root"]
            logical_content = "\n\n".join(
                block.raw_content.strip()
                for block in group["blocks"]
                if block.raw_content.strip()
            )
            parts = _split_oversized(logical_content)
            page_start = min(block.page_start for block in group["blocks"])
            page_end = max(block.page_end for block in group["blocks"])

            for split_index, content in enumerate(parts):
                chunk_key = f"{version_key}::c::{child_counter:04d}"
                point_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"ctu-student-service/chunk/{version_key}/{chunk_key}",
                    )
                )
                item_path = list(root.item_path)
                logical_item_keys = (
                    [root.logical_item_key]
                    if root.block_type == "bullet_item" and root.logical_item_key
                    else []
                )
                structural = {
                    "block_type": root.block_type,
                    "legal_unit_type": root.legal_unit_type,
                    "item_path": item_path,
                    "logical_item_key": root.logical_item_key,
                    "logical_item_keys": logical_item_keys,
                    "parent_item_key": root.parent_item_key,
                    "logical_table_key": root.logical_table_key,
                    "logical_code_key": root.logical_code_key,
                    "split_index": split_index,
                    "split_count": len(parts),
                    "item_marker": root.item_marker,
                    "item_level": root.item_level,
                    "source_order": root.source_order,
                }
                embed_text = _embedding_text(
                    frontmatter,
                    root,
                    parent["heading_path"],
                    content,
                    page_start,
                    page_end,
                )
                payload = {
                    "document_key": document_key,
                    "version_key": version_key,
                    "title": frontmatter["title"],
                    "source_file": source_file,
                    "source_url": frontmatter.get("source_url") or None,
                    "document_type": frontmatter["document_type"],
                    "domain": frontmatter["domain"],
                    "audience": ["sinh_vien"],
                    "audience_student": True,
                    "review_status": "approved",
                    "rag_status": "published",
                    "is_latest": True,
                    "chunk_key": chunk_key,
                    "parent_chunk_key": parent_key,
                    "chunk_type": "child",
                    "heading_path": parent["heading_path"],
                    "item_path": item_path,
                    "page_start": page_start,
                    "page_end": page_end,
                    **{key: value for key, value in structural.items() if key != "source_order"},
                    "chunk_index": chunk_index,
                }
                records.append(
                    {
                        "postgres": {
                            "chunk_key": chunk_key,
                            "parent_chunk_key": parent_key,
                            "chunk_index": chunk_index,
                            "chunk_type": "child",
                            "heading_path": parent["heading_path"],
                            "section_title": parent["heading_path"][-1],
                            "content": content,
                            "page_start": page_start,
                            "page_end": page_end,
                            "token_count": len(content.split()),
                            "qdrant_point_id": point_id,
                            "index_status": "indexed",
                        },
                        "structural": structural,
                        "embedding": {
                            "model": "BAAI/bge-m3",
                            "vector_name": "embedding",
                            "dimension": 1024,
                            "normalize": True,
                            "text": embed_text,
                            "text_sha256": hashlib.sha256(
                                embed_text.encode("utf-8")
                            ).hexdigest(),
                        },
                        "qdrant": {
                            "id": point_id,
                            "vector_name": "embedding",
                            "vector_from": "embedding.text",
                            "postgres_refs": {
                                "postgres_chunk_id": chunk_key,
                                "postgres_parent_chunk_id": parent_key,
                            },
                            "payload_template": payload,
                        },
                    }
                )
                child_counter += 1
                chunk_index += 1

    return records


def build_fixture(source: Path) -> dict:
    raw_bytes, metadata, pages, parsed = _read_source(source)
    parents = _parent_groups(parsed.blocks)
    records = _build_chunk_records(metadata, parents, source.name)
    canonical_checksum = hashlib.sha256(raw_bytes).hexdigest()
    source_path = "Dataset/06_Processing/01_OCR_Output/PDFs_CTSV/QuyetDinh/" + source.name

    return {
        "fixture_version": "1.0",
        "purpose": "Expected PostgreSQL + embedding + Qdrant seed for QD3266 retrieval tests",
        "contract": ".docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md",
        "source": {
            "path": source_path,
            "file_name": source.name,
            "sha256": canonical_checksum,
            "page_count": len(pages),
        },
        "normalizations": [
            {
                "field": "audience",
                "source": metadata.get("audience"),
                "fixture": ["sinh_vien"],
                "reason": "Map OCR label to the public Audience enum.",
            },
            {
                "field": "effective_date",
                "source": _iso(metadata.get("effective_date")),
                "fixture_target": "postgres.document_recipients[*].effective_date",
                "reason": "document_versions has no effective_date column.",
            },
            {
                "field": "checksum",
                "source": metadata.get("checksum"),
                "fixture": canonical_checksum,
                "reason": "Use SHA-256 of the canonical Markdown fixture source.",
            },
            {
                "field": "page_boundary_artifacts",
                "source": "horizontal rule plus next page number around page markers",
                "fixture": "removed before structural parsing",
                "reason": "Boundary artifacts are not retrievable content.",
            },
            {
                "field": "rag_status",
                "source": metadata.get("rag_status"),
                "fixture": "published",
                "reason": "Fixture represents the final state needed by retrieval.",
            },
        ],
        "load_order": [
            "Insert postgres.document and postgres.document_version.",
            "Insert Parent chunks and capture their generated IDs.",
            "Insert Child chunks after resolving parent_chunk_key; capture Child IDs.",
            "Embed embedding.text for every Child.",
            "Resolve qdrant.postgres_refs into payload postgres IDs.",
            "Upsert qdrant.id with named vector embedding and the resolved payload.",
        ],
        "postgres": {
            "document": {
                "document_key": metadata["document_key"],
                "title": metadata["title"],
                "domain": metadata["domain"],
                "audience": ["sinh_vien"],
                "document_type_code": metadata["document_type"],
            },
            "document_version": {
                "version_key": metadata["version_key"],
                "title": metadata["title"],
                "code": metadata.get("code"),
                "issued_date": _iso(metadata.get("issued_date")),
                "issuing_authority": metadata.get("issuing_authority"),
                "signer_name": metadata.get("signer_name"),
                "is_latest": True,
                "source_url": metadata.get("source_url") or "",
                "source_path": metadata.get("source_path") or "",
                "canonical_markdown_path": source_path,
                "file_type": metadata.get("file_type", "pdf"),
                "language": metadata.get("language", "vi"),
                "accessed_date": _iso(metadata.get("accessed_date")),
                "checksum": canonical_checksum,
                "extra_metadata": {
                    "parser": metadata.get("parser"),
                    "ocr_engine": metadata.get("ocr_engine"),
                    "notes": metadata.get("notes"),
                    "source_frontmatter_checksum": metadata.get("checksum"),
                    "fixture_normalized": True,
                },
                "ocr_status": "done",
                "review_status": "approved",
                "rag_status": "published",
                "status_note": "QD3266 retrieval fixture",
            },
            "document_recipients": [
                {
                    "department_code": code,
                    "effective_date": _iso(
                        metadata.get("effective_date") or metadata.get("issued_date")
                    ),
                }
                for code in metadata["responsible_department"]
            ],
        },
        "chunking": {
            "page_marker_cleanup": True,
            "parser": "backend/app/ingestion/parsing/structural_parser.py",
            "child_chunk_size_chars": CHUNK_SIZE,
            "child_chunk_overlap_chars": CHUNK_OVERLAP,
            "parent_rule": "document-root before first heading; every heading opens a Parent",
            "child_rule": "item/paragraph/table Child; owned paragraphs join their item; split oversized content",
        },
        "qdrant_contract": {
            "collection": "ctu_chunks_bge_m3",
            "vector_name": "embedding",
            "dimension": 1024,
            "distance": "Cosine",
            "points": "Child only",
            "payload_content_forbidden": True,
            "payload_ids_to_resolve_after_postgres_insert": [
                "postgres_chunk_id",
                "postgres_parent_chunk_id",
            ],
        },
        "chunks": records,
        "expected": {
            "postgres_chunk_rows": len(records),
            "parent_chunks": sum(
                row["postgres"]["chunk_type"] == "parent" for row in records
            ),
            "child_chunks": sum(
                row["postgres"]["chunk_type"] == "child" for row in records
            ),
            "embedding_jobs": sum(row["embedding"] is not None for row in records),
            "qdrant_points": sum(row["qdrant"] is not None for row in records),
            "structural_reports": len(parsed.reports),
        },
    }


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    fixture = build_fixture(source)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    expected = fixture["expected"]
    assert expected == {
        "postgres_chunk_rows": 313,
        "parent_chunks": 54,
        "child_chunks": 259,
        "embedding_jobs": 259,
        "qdrant_points": 259,
        "structural_reports": 0,
    }
    assert all(
        "content" not in row["qdrant"]["payload_template"]
        for row in fixture["chunks"]
        if row["qdrant"] is not None
    )
    print(OUTPUT)
    print(json.dumps(expected, ensure_ascii=False))


if __name__ == "__main__":
    main()
