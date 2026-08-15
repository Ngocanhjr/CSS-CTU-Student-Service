import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.ingestion.canonical_storage import MAX_SOURCE_BYTES
from app.ocr.engines.llamaparse_engine import SUPPORTED_INPUT_EXTENSIONS
from app.ocr.service import ocr_document
from app.schemas.ocr import OcrDocumentResponse


router = APIRouter(prefix="/admin/ocr", tags=["admin-ocr"])


@router.post("", response_model=OcrDocumentResponse)
async def run_ocr(file: UploadFile = File(...)) -> OcrDocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file OCR bị thiếu")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_INPUT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_INPUT_EXTENSIONS))
        raise HTTPException(status_code=422, detail=f"Định dạng OCR không hỗ trợ. Dùng: {supported}")

    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        raise HTTPException(status_code=503, detail="OCR chưa được cấu hình LLAMA_CLOUD_API_KEY")

    try:
        content = await file.read(MAX_SOURCE_BYTES + 1)
        if not content:
            raise ValueError("File OCR rỗng")
        if len(content) > MAX_SOURCE_BYTES:
            raise ValueError(f"File OCR vượt quá {MAX_SOURCE_BYTES // 1024 // 1024} MB")

        with TemporaryDirectory(prefix="ctu-ocr-") as temporary_directory:
            input_path = Path(temporary_directory) / f"source{suffix}"
            input_path.write_bytes(content)
            return await run_in_threadpool(
                ocr_document,
                input_path,
                source_filename=Path(file.filename).name,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OCR thất bại; vui lòng thử lại") from exc
    finally:
        await file.close()
