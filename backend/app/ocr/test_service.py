from pathlib import Path

from app.ocr.engines.llamaparse_engine import ParsedPage
from app.ocr.service import ocr_document


class FakeEngine:
    def parse_pages(self, _path, _options):
        return [ParsedPage(page_number=1, text="# Nội dung OCR")]


def test_ocr_document_returns_reviewable_markdown(tmp_path: Path) -> None:
    source = tmp_path / "Phiếu đăng ký.pdf"
    source.write_bytes(b"%PDF-test")

    result = ocr_document(source, source_filename=source.name, engine=FakeEngine())

    assert result.source_filename == source.name
    assert result.markdown.startswith("---\n")
    assert "<!-- page: 1 -->" in result.markdown
    assert "# Nội dung OCR" in result.markdown
    assert result.metadata["document_key"] == "ctu-phieu-dang-ky"
    assert result.metadata["version_key"].startswith("ctu-phieu-dang-ky-")
    assert result.metadata["checksum"]
    assert result.metadata["source_path"] == source.name
    assert str(tmp_path) not in result.markdown
