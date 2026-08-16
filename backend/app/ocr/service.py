from pathlib import Path

from app.ocr.engines.llamaparse_engine import LlamaParseRawEngine, RawParseOptions
from app.ocr.postprocess.llamaparse_postprocess import postprocess_llamaparse_markdown
from app.ocr.postprocess.page_formatter import render_pages
from app.ocr.validation.apply_metadata import (
    apply_metadata_to_markdown,
    dump_front_matter,
    split_front_matter,
)
from app.schemas.ocr import OcrDocumentResponse


def ocr_document(
    input_path: Path,
    *,
    source_filename: str,
    engine: LlamaParseRawEngine | None = None,
) -> OcrDocumentResponse:
    """OCR one temporary source file without persistence side effects."""

    parser = engine or LlamaParseRawEngine()
    pages = parser.parse_pages(input_path, RawParseOptions())
    if not pages:
        raise ValueError("OCR không trả về nội dung")

    ocr_markdown = postprocess_llamaparse_markdown(render_pages(pages)).strip()
    if not ocr_markdown:
        raise ValueError("OCR không trả về nội dung")

    output_name = f"{Path(source_filename).stem}_ocr.md"
    markdown = apply_metadata_to_markdown(
        ocr_markdown,
        md_path=input_path.with_name(output_name),
        source_file=input_path,
        language="vi",
        ocr_status="done",
        parser="llamaparse_postprocessed",
        ocr_engine="LlamaParse API",
    )
    metadata, body = split_front_matter(markdown)

    # File chỉ tồn tại trong request. Không đưa đường dẫn temp của server vào
    # bản OCR mà admin xem; đường dẫn R2 canonical sẽ được tạo lúc bấm Lưu.
    metadata.update(
        {
            "source_path": Path(source_filename).name,
            "canonical_markdown_path": output_name,
            "review_status": "reviewing",
            "rag_status": "not_indexed",
        }
    )
    markdown = dump_front_matter(metadata) + body

    return OcrDocumentResponse(
        source_filename=source_filename,
        markdown=markdown.rstrip() + "\n",
        metadata=metadata,
    )
