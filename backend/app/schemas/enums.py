from typing import Literal

"""
CollectionStatus mô tả trạng thái thu thập nguồn/file trước OCR và ingestion.

- link_collected: mới ghi nhận link nguồn.
- collected: đã có đủ nguồn/file để xử lý tiếp.
- downloaded: file đã được tải về workspace/vault.
- missing: thiếu nguồn/file cần thiết.
- failed: thu thập hoặc tải nguồn thất bại.
"""

CollectionStatus = Literal[
    "link_collected", 
    "collected", 
    "downloaded", 
    "missing", 
    "failed"
]

"""
OcrStatus mô tả trạng thái OCR/parser trước khi tài liệu được review và đưa vào RAG.

- not_started: chưa chạy OCR/parser.
- processing: đang chạy OCR/parser.
- done: OCR/parser đã hoàn tất và có output Markdown.
- failed: OCR/parser thất bại, chưa có output dùng được.
- need_review: OCR/parser có output nhưng cần kiểm tra kỹ hoặc sửa thủ công.
"""

OcrStatus = Literal [
    "not_started", 
    "processing", 
    "done", 
    "failed", 
    "need_review", 
]

"""
ReviewStatus mô tả trạng thái kiểm tra nội dung sau OCR/parser.

- not_reviewed: chưa có người kiểm tra nội dung.
- reviewing: đang được kiểm tra.
- need_fix: đã kiểm tra và cần sửa nội dung/metadata.
- approved: đã duyệt, đủ điều kiện xét publish nếu hiệu lực hợp lệ.
- rejected: bị loại bỏ, không dùng cho RAG.
"""

ReviewStatus = Literal [
    "not_reviewed", 
    "reviewing", 
    "need_fix", 
    "approved", 
    "rejected"
]
"""
ValidityStatus mô tả tình trạng hiệu lực pháp lý/nghiệp vụ của tài liệu.

- unchecked: chưa kiểm tra hiệu lực.
- valid: còn hiệu lực, có thể dùng nếu đã review và publish.
- expired: đã hết hiệu lực theo ngày hoặc quy định.
- replaced: đã bị tài liệu/version khác thay thế.
- unknown: đã kiểm tra nhưng chưa xác định được hiệu lực.
"""

ValidityStatus = Literal [
    "unchecked", 
    "valid", 
    "expired", 
    "replaced", 
    "unknown"
]

"""
RagStatus mô tả trạng thái của tài liệu trong pipeline RAG.

- not_indexed: chưa đưa vào pipeline RAG.
- chunked: đã chia chunk và lưu metadata chunk.
- embedded: đã tạo embedding cho chunk.
- indexed: đã đưa vector vào vector DB như Qdrant.
- published: đang được retriever/chatbot sử dụng.
- deactivated: đã ngưng dùng trong truy xuất RAG.
- failed: lỗi trong quá trình chunk/embed/index.
"""
RagStatus = Literal [
    "not_indexed", 
    "chunked", 
    "embedded", 
    "indexed", 
    "published", 
    "deactivated", 
    "failed"
]

DocumentType = Literal [
    "noi_quy",
    "quy_trinh",
    "bieu_mau",
    "hoi_dap",
    "ke_hoach",
    "thong_bao",
    "unknown",
]

"""
DocumentAssetRelationType mô tả quan hệ giữa document version và asset đi kèm.

- required_form: biểu mẫu bắt buộc cho thủ tục/tài liệu.
- reference: tài liệu/file tham khảo.
- supplement: file bổ sung cho nội dung chính.
- guide: hướng dẫn sử dụng hoặc hướng dẫn thực hiện.
"""
DocumentAssetRelationType = Literal[
    "required_form",
    "reference",
    "supplement",
    "guide",
]

"""
AssetType mô tả loại asset/file phụ trợ.

- form: biểu mẫu cần điền hoặc tải về.
- template: mẫu tài liệu.
- guide: file hướng dẫn.
- attachment: file đính kèm khác.
"""
AssetType = Literal[
    "form",
    "template",
    "guide",
    "attachment",
]

"""
VersionRole mô tả vai trò của một version tài liệu trong quan hệ version.

- base: bản gốc hoặc bản nền, có thể vẫn còn hiệu lực nếu chỉ bị sửa đổi/bổ sung một phần.
- replacement: bản thay thế toàn bộ một hoặc nhiều version cũ; version cũ thường chuyển sang validity_status = replaced.
- amendment: bản sửa đổi một phần version khác; bản gốc có thể vẫn valid và cần được truy xuất cùng bản sửa đổi.
- supplement: bản bổ sung một phần version khác; bản gốc có thể vẫn valid và cần được truy xuất cùng bản bổ sung.
"""
VersionRole = Literal [
    "base", 
    "replacement", 
    "amendment", 
    "supplement"
]

DocumentRelationshipType = Literal[
    "replaces",
    "amends",
    "supplements",
]

FileType = Literal[
    "pdf",
    "doc",
    "docx",
    "image",
    "xlsx",
    "pptx",
    "txt",
    "md",
    "html",
    "csv",
    "url",
    "youtube",
]

CitationType = Literal[
    "page", 
    "section", 
    "paragraph"
]

ChunkType = Literal["parent", "child"]


EmbeddingStatus = Literal[
    "pending",
    "embedded",
    "failed",
    "skipped",
]

QdrantStatus = Literal[
    "not_indexed",
    "indexed",
    "deactivated",  
    "failed",
]    

Domain = Literal[
    "hoc_vu",
    "hoc_phi",
    "dao_tao",
    "nghien_cuu_khoa_hoc",
    "hop_tac_quoc_te",
    "hoc_bong",
    "sinh_vien",
]
