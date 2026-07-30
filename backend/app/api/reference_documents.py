from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(
    prefix="/api/v1/reference-documents",
    tags=["Reference documents"],
)

BASE_DIR = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = BASE_DIR / "storage" / "reference_documents"


DOCUMENTS = {
    1: {
        "id": 1,
        "title": "Quy chế đào tạo trình độ đại học",
        "description": "Tài liệu tham khảo về quy định đào tạo.",
        "pdf_file": "quy_che_dao_tao.pdf",
        "markdown_file": "quy_che_dao_tao.md",
    },
    2: {
        "id": 2,
        "title": "Thông tin học bổng sinh viên",
        "description": "Tài liệu tham khảo về học bổng.",
        "pdf_file": "hoc_bong.pdf",
        "markdown_file": "hoc_bong.md",
    },
}


@router.get("")
def get_reference_documents():
    """Trả về danh sách tài liệu tham khảo."""

    return [
        {
            "id": document["id"],
            "title": document["title"],
            "description": document["description"],
            "pdf_url": (
                f"/api/v1/reference-documents/"
                f"{document['id']}/pdf"
            ),
            "content_url": (
                f"/api/v1/reference-documents/"
                f"{document['id']}/content"
            ),
        }
        for document in DOCUMENTS.values()
    ]


@router.get("/{document_id}/pdf")
def view_reference_pdf(document_id: int):
    """Mở PDF trực tiếp trên trình duyệt."""

    document = DOCUMENTS.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài liệu.",
        )

    pdf_path = DOCUMENT_DIR / document["pdf_file"]

    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy file PDF.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=document["pdf_file"],
        content_disposition_type="inline",
    )


@router.get("/{document_id}/content")
def get_reference_content(document_id: int):
    """Trả về nội dung OCR Markdown."""

    document = DOCUMENTS.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài liệu.",
        )

    markdown_path = DOCUMENT_DIR / document["markdown_file"]

    if not markdown_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy nội dung OCR.",
        )

    content = markdown_path.read_text(encoding="utf-8")

    return {
        "id": document_id,
        "title": document["title"],
        "content": content,
    }