from pathlib import Path

from app.ocr.engines.llamaparse_engine import ParsedPage
from app.ocr.service import ocr_document


class FakeEngine:
    def parse_pages(self, _path, _options):
        return [ParsedPage(page_number=1, text="# Nội dung OCR")]


def test_ocr_document_returns_reviewable_markdown(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-test")

    result = ocr_document(source, source_filename="source.pdf", engine=FakeEngine())

    assert result.source_filename == "source.pdf"
    assert "<!-- page: 1 -->" in result.markdown
    assert "# Nội dung OCR" in result.markdown
