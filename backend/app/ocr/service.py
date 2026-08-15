from pathlib import Path

from app.ocr.engines.llamaparse_engine import LlamaParseRawEngine, RawParseOptions
from app.ocr.postprocess.llamaparse_postprocess import postprocess_llamaparse_markdown
from app.ocr.postprocess.page_formatter import render_pages
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

    markdown = postprocess_llamaparse_markdown(render_pages(pages)).strip()
    if not markdown:
        raise ValueError("OCR không trả về nội dung")

    return OcrDocumentResponse(
        source_filename=source_filename,
        markdown=f"{markdown}\n",
    )
