`docker compose exec postgres psql -U ct239h -d ctu_student_service -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"`
nếu không có schema hoặc đã tạo postgres trước đó
`docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dn"`
kiểm tra schema

- [x] PostgreSQL chạy được
- [ ] Chunk Pydantic model
  - app/schemas/enums.py
  - app/schemas/rag.py
- [ ] Markdown chunker
- [ ] Preview chunk từ file OCR thật
- [ ] Chốt schema fields
- [ ] SQLAlchemy models
- [ ] Alembic migration chạy được
- [ ] Insert metadata/chunks vào PostgreSQL
- [ ] Embed child chunks
- [ ] Upsert Qdrant

---

- [x] 1. PostgreSQL chạy được
  - Container healthy
  - Kết nối được ctu_student_service
  - Schema `css` tồn tại

- [ ] 2. Xác định draft fields cho chunk
  - document_id
  - version_id
  - chunk_id
  - parent_chunk_id
  - chunk_type
  - content
  - heading_path
  - page_start
  - page_end
  - chunk_index
  - token_count

- [ ] 3. Tạo Chunk Pydantic model
  - Validate field bắt buộc
  - Validate page và chunk_index
  - Phân biệt parent/child chunk

    ```bash
    Pydantic Chunk
        ↓ chuyển đổi
    LangChain Document
        ↓
    Embedding / Qdrant
    ```

    - Pydantic Chunk: cấu trúc dữ liệu chuẩn của hệ thống.
    - LangChain Document: định dạng truyền dữ liệu vào LangChain.
    - SQLAlchemy DocumentChunk: định dạng lưu PostgreSQL.

- [ ] 4. Viết Markdown chunker
  - Đọc heading Markdown
  - Nhận diện <!-- page: N -->
  - Tạo parent chunk theo section
  - Chia child chunk theo kích thước
  - Giữ metadata kế thừa

- [ ] 5. Preview chunk từ file OCR thật
  - In ra JSON hoặc Markdown
  - Kiểm tra mất nội dung
  - Kiểm tra heading_path
  - Kiểm tra page_start/page_end
  - Kiểm tra chunk quá ngắn hoặc quá dài

- [ ] 6. Chốt schema fields
  - Field lưu trong PostgreSQL
  - Field lưu trong Qdrant payload
  - Field chỉ dùng tạm trong pipeline

- [ ] 7. Tạo SQLAlchemy models
  - documents
  - document_versions
  - document_chunks

- [ ] 8. Tạo và chạy Alembic migration
  - alembic revision --autogenerate
  - alembic upgrade head
  - Kiểm tra bảng trong rag.\*

- [ ] 9. Insert metadata và chunks vào PostgreSQL
  - Insert document
  - Insert document version
  - Insert parent/child chunks
  - rag_status = not_indexed hoặc pending

- [ ] 10. Embed child chunks
  - Dùng thống nhất BAAI/bge-m3
  - Không embed parent chunk ở giai đoạn đầu
  - Lưu embedding_model và embedding_version

- [ ] 11. Upsert vào Qdrant
  - Vector của child chunk
  - Payload chứa PostgreSQL IDs
  - Không xem Qdrant là nguồn metadata chính

- [ ] 12. Cập nhật trạng thái sau indexing
  - Thành công: rag_status = indexed/activated
  - Thất bại: rag_status = failed
  - Lưu error_message hoặc ingestion job log
