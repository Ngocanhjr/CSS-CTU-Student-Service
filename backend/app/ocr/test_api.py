from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ocr import router
from app.schemas.ocr import OcrDocumentResponse


def test_ocr_endpoint_returns_markdown_without_persistence(monkeypatch) -> None:
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-key")

    def fake_ocr_document(path, *, source_filename):
        assert path.read_bytes() == b"%PDF-test"
        assert path.name == "Phiếu đăng ký.pdf"
        return OcrDocumentResponse(
            source_filename=source_filename,
            markdown="---\ndocument_key: ctu-phieu-dang-ky\n---\n# OCR\n",
            metadata={"document_key": "ctu-phieu-dang-ky"},
        )

    monkeypatch.setattr("app.api.ocr.ocr_document", fake_ocr_document)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    response = TestClient(app).post(
        "/api/v1/admin/ocr",
        files={"file": ("Phiếu đăng ký.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["source_filename"] == "Phiếu đăng ký.pdf"
    assert response.json()["metadata"]["document_key"] == "ctu-phieu-dang-ky"


def test_ocr_endpoint_logs_unexpected_engine_error(monkeypatch, caplog) -> None:
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-key")

    def fail_ocr_document(_path, *, source_filename):
        raise RuntimeError(f"engine failed for {source_filename}")

    monkeypatch.setattr("app.api.ocr.ocr_document", fail_ocr_document)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with caplog.at_level("ERROR", logger="app.api.ocr"):
        response = TestClient(app).post(
            "/api/v1/admin/ocr",
            files={"file": ("source.pdf", b"%PDF-test", "application/pdf")},
        )

    assert response.status_code == 502
    assert "OCR failed for source file source.pdf" in caplog.text
    assert "RuntimeError: engine failed for source.pdf" in caplog.text
