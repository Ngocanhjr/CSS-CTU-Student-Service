# Chứa các enum như loại tài liệu, trạng thái xử lý, loại chunk.

from typing import Literal

"""
CollectionStatus mô tả trạng thái thu thập nguồn/file trước OCR và ingestion.

- link_collected: mới ghi nhận link nguồn.
- collected: đã có đủ nguồn/file để xử lý tiếp.
- downloaded: file đã được tải về workspace/vault.
- missing: thiếu nguồn/file cần thiết.
- failed: thu thập hoặc tải nguồn thất bại.
"""

# CollectionStatus = Literal[
#     "link_collected", 
#     "collected", 
#     "downloaded", 
#     "missing", 
#     "failed"
# ]

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

# ValidityStatus = Literal [
#     "unchecked", 
#     "valid", 
#     "expired", 
#     "replaced", 
#     "unknown"
# ]

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
    "bao_cao",
    "huong_dan",
    "quyet_dinh",
    "cong_van",
    "thong_tu",
    "nghi_quyet",
    "unknown",
]

Audience = Literal[
    "sinh_vien",
    "can_bo",
    "giang_vien",
    "cong_khai",
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

DocumentAssetRelationType = Literal[
    "reference",  # tài liệu tham khảo
    "attachment", # tài liệu đính kèm
    "template",   # tài liệu mẫu
    "guide",      # tài liệu hướng dẫn
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
    "giang_vien",
    "can_bo",
    "tuyen_sinh",
    "vh_xh",
    "ne_nep",
    "unknown",
    "nghi_hoc",
    "dinh_chi",
]

signer_name = Literal[
    "HT" # Hiệu trưởng
    "PHT" # Phó hiệu trưởng
    "TT" # Thứ trưởng
    "TP" # Trưởng phòng
    "CT" # Chủ tịch
]

responsible_department = Literal[
    "PHTQT" #phòng hơp tác quốc tế 
    "PDT" # phòng đào tạo
    "PCTSV" # phòng công tác sinh viên
    "PKHTH" # phòng kế hoạch tổng hợp
    "PKHTC" # phòng kế hoạch tài chính
    "PTV" # phòng tài vụ
    "PTCCB" # phòng tổ chức cán bộ
    "PTC"  # phòng tài chính
    "PQTTB" # phòng quản trị thiết bị
    "PQLKH" # phòng quản lý khoa học
    "PTTPC" # phòng thanh tra pháp chế
    "PTCPTNS" # phòng tổ chức cán bộ và phát triển nhân sự
    "PCTCT" # phòng công tác chính trị
    "TTGDQP&AN" # trung tâm giáo dục quốc phòng và an ninh
    "TTQLCL" # trung tâm quản lý chất lượng
    "TTHL" # trung tâm học liệu
    "TTTT&QTM" # trung tâm thông tin và quản trị mạng
    "TTDGNLNN" # trung tâm đánh giá năng lực ngoại ngữ
    "TTLKDT" # trung tâm liên kết đào tạo
    "TTPVSV" # trung tâm phục vụ sinh viên
    "KNN" # khoa ngoai ngữ
    "KDBDT" # khoa dự bị dân tộc
    "KSDH" # khoa sau đại học
    "KGDTC" # khoa giáo dục thể chất
    "VPTr" # văn phòng trường
    "DVQLN" # đơn vị quản lý ngành
    "HDXMCNDHP" # hội đồng xét miễn và công nhận điểm học phần
    "HDDGNLNN" # hội đồng đánh giá năng lực ngoại ngữ
    "BGDDT" # bộ giáo dục và đào tạo
    
    "BO"        # Các Bộ trưởng / các Bộ
    "CQNB"      # Cơ quan ngang bộ
    "CQCP"      # Cơ quan thuộc Chính phủ
    "UBND-TT"   # Ủy ban nhân dân tỉnh, thành phố trực thuộc trung ương
    "NHCSXH"    # Ngân hàng Chính sách xã hội
]

BlockType = Literal[
    "heading",
    "numbered_item",
    "lettered_item",
    "bullet_item",
    "paragraph",
    "table",
    "code",
]

Severity = Literal["warning", "error"]
