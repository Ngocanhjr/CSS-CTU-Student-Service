
**1/ Upload tài liệu:**

[Bắt đầu]
    ↓
[Admin mở trang Xử lý tài liệu]
    ↓
{Đã có file Markdown?}

 ├── Có
 │     ↓
 │  [Upload Markdown]
 │     ↓
 │  [Nhập metadata]
 │
 └── Không
       ↓
    [Mở trang OCR]
       ↓
    [Upload PDF/DOC/DOCX/PPT/PPTX/ảnh]
       ↓
    [Bắt đầu OCR]
       ↓
    {OCR thành công?}
       ├── Không → [Hiển thị lỗi] → [Thử lại hoặc chọn file khác]
       └── Có
             ↓
          [Hiển thị Markdown kết quả]
             ↓
          [Admin review/chỉnh Markdown]
             ↓
          [Nhập metadata ngay trên trang OCR]

Hai nhánh hội tụ
       ↓
[Admin bấm “Lưu và tiếp tục”]
       ↓
[Validate Markdown và metadata]
       ↓
{Dữ liệu hợp lệ?}
 ├── Không → [Hiển thị lỗi] → [Admin chỉnh sửa]
 └── Có
       ↓
    [Lưu file nguồn và canonical Markdown vào R2]
       ↓
    [Tạo document/version/job trong PostgreSQL]
       ↓
    [Review và phê duyệt tài liệu]
       ↓
    [Preview và phê duyệt chunks]
       ↓
    [Index document version vào Qdrant]
       ↓
    [Publish document version]
       ↓
    [Hoàn tất]


---



**2/ Review& Approve:**

[Bắt đầu]
    ↓
[Tài liệu đã được lưu sau bước Upload/OCR]

Trạng thái ban đầu:
ocr_status = done
review_status = reviewing
rag_status = not_indexed
    ↓
[Admin mở trang Review & approve]
    ↓
[Hệ thống hiển thị]
 ├── Metadata
 ├── File nguồn
 ├── Canonical Markdown đã lưu
 ├── Nội dung Markdown để chỉnh sửa
 └── Assets đính kèm
    ↓
[Admin kiểm tra tài liệu]
 ├── Mở file nguồn
 ├── Mở/tải canonical Markdown
 ├── Chỉnh metadata
 ├── Chỉnh Markdown
 └── Thêm/sửa assets nếu cần
    ↓
[Admin bấm “Lưu và duyệt sang Review chunks”]
    ↓
[Validate dữ liệu]
 ├── Markdown không được rỗng
 ├── Tiêu đề bắt buộc
 ├── Loại tài liệu hợp lệ
 ├── Phòng ban phụ trách hợp lệ
 └── Assets phải đủ tiêu đề, URL và loại
    ↓
{Dữ liệu hợp lệ?}

 ├── Không
 │     ↓
 │  [Hiển thị lỗi]
 │     ↓
 │  [Admin tiếp tục chỉnh sửa]
 │
 └── Có
       ↓
    [Kiểm tra version chưa được index]
       ↓
    {rag_status = not_indexed?}

├── Không
       │     ↓
       │  [Chặn approve]
       │  [Yêu cầu de-index trước]
       │
       └── Có
             ↓
          [Tạo canonical Markdown revision mới]
             ↓
          [Lưu revision mới vào R2]
             ↓
          [Cập nhật PostgreSQL]
             ├── Metadata mới
             ├── canonical_markdown_path mới
             ├── Assets
             ├── review_status = approved
             ├── rag_status = not_indexed
             └── ingestion_job.current_step = chunking
             ↓
          [Xóa canonical revision cũ khỏi R2]
             ↓
          [Chuyển sang Review chunks]
             ↓
          [Kết thúc]

---

**3/ Preview & approve chunks:**

[Tạo chunk preview]
    ↓
[Admin kiểm tra chunks]
    ↓
[Admin bấm Approve chunks]
    ↓
[Backend tạo/validate lại đúng bộ chunks]
    ↓
{Có errors?}
 ├── Có → [Không cho approve]
 └── Không
       ↓
    [Transaction PostgreSQL]
       ├── Replace Parent chunks
       ├── Replace Child chunks
       ├── index_status = not_indexed
       ├── Lưu tổng số chunks
       └── Đánh dấu current_step = chunks_approved
       ↓
    [Trả kết quả approve]
       ↓
    [Chuyển sang Index & publish]



---


**4/ Index&Publish**

[Admin chọn document version đã publish]
    ↓
[Admin chọn Unpublish]
    ↓
[Hiển thị xác nhận]
    ↓
{Admin xác nhận?}
 ├── Không → [Hủy thao tác]
 └── Có
       ↓
    {rag_status = published?}
       ├── Không → [Thông báo trạng thái không hợp lệ]
       └── Có
             ↓
          [PostgreSQL:
           rag_status = indexed
           lưu unpublished_at]
             ↓
          [Qdrant:
           cập nhật payload rag_status = indexed]
             ↓
          {Qdrant cập nhật thành công?}
             ├── Không
             │     ↓
             │  [Khôi phục PostgreSQL về published]
             │  [Xóa unpublished_at]
             │  [Hiển thị lỗi]
             └── Có
                   ↓
                [Tài liệu bị ẩn khỏi chatbot]
                   ↓
                [Chunks và vectors vẫn được giữ]

---


**5/ Deindex version:**

[Admin chọn document version đã index/publish]
    ↓
[Admin chọn Deindex]
    ↓
[Thông báo: sẽ xóa chunks và vectors]
    ↓
{Admin xác nhận?}
 ├── Không → [Hủy thao tác]
 └── Có
       ↓
    {Có indexing job đang chạy?}
       ├── Có → [Chặn Deindex]
       └── Không
             ↓
          {rag_status thuộc
           chunked/embedded/indexed/published?}
             ├── Không → [Thông báo tài liệu chưa được index]
             └── Có
                   ↓
                [Tạo deindex job]
                   ├── status = processing
                   ├── current_step = qdrant_delete
                   └── rag_status = deactivated
                   ↓
                [Xóa vectors khỏi Qdrant]
                   ↓
                {Xóa Qdrant thành công?}
                   ├── Không
                   │     ↓
                   │  [job_status = failed]
                   │  [Giữ rag_status = deactivated]
                   │  [Cho phép thử lại Deindex]
                   └── Có
                         ↓
                      [Xóa chunks khỏi PostgreSQL]
                         ↓
                      [Cập nhật trạng thái]
                         ├── rag_status = not_indexed
                         ├── job_status = completed
                         └── current_step = completed
                         ↓
                      [Hoàn tất Deindex]

---


**6/ Delete version:**

[Admin chọn document version]
    ↓
{rag_status = not_indexed hoặc failed?}

 ├── Không
 │     ↓
 │  [Chặn Delete]
 │     ↓
 │  [Yêu cầu Deindex trước]
 │
 └── Có
       ↓
    [Admin chọn Delete]
       ↓
    [Hiển thị cảnh báo xóa dữ liệu liên quan]
       ↓
    {Admin xác nhận?}
       ├── Không → [Hủy thao tác]
       └── Có
             ↓
          [Tạo delete job]
             ├── status = processing
             ├── current_step = external_cleanup
             └── rag_status = deactivated
             ↓
          [Dọn dữ liệu external]
             ├── Xóa vectors Qdrant còn sót
             ├── Xóa canonical Markdown khỏi R2
             └── Xóa file nguồn khỏi R2
             ↓
          {Dọn dữ liệu thành công?}
             ├── Không
             │     ↓
             │  [job_status = failed]
             │  [Giữ trạng thái deactivated]
             │  [Admin chọn Thử lại Delete]
             └── Có
                   ↓
                [Xóa document version khỏi PostgreSQL]
                   ↓
                {Document còn version khác?}
                   ├── Có → [Giữ document]
                   └── Không → [Xóa luôn document]
                   ↓
                [Hoàn tất]
