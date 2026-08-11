# 01. Pydantic Schema Implementation Guide

Guide này chỉ hướng dẫn public DTO và validation. Không định nghĩa lại PostgreSQL DDL hoặc Qdrant
payload. Physical contract nằm tại:

```text
.docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md
```

## Phạm vi

Kiểm tra các file hiện có trước khi sửa:

```text
backend/app/schemas/base.py
backend/app/schemas/enums.py
backend/app/schemas/documents.py
backend/app/schemas/assets.py
backend/app/schemas/chunks.py
backend/app/schemas/ingestion/
```

## Quy tắc

- Schema tại trust boundary dùng validation chặt; không âm thầm nhận enum sai.
- YAML/API/RAG dùng stable keys: `document_key`, `version_key`, `chunk_key`, `asset_key`.
- PostgreSQL integer IDs không xuất hiện trong YAML metadata.
- API response dùng DTO riêng; không serialize ORM model trực tiếp.
- Không thêm field vì “có thể cần sau này”. Field mới phải có consumer và mapping rõ.
- Giá trị enum phải lấy từ `schemas/enums.py`; Contract 10 quyết định giá trị dùng xuyên store.

## Document metadata

`DocumentMetadata` chịu trách nhiệm:

- validate metadata canonical Markdown;
- chuẩn hóa list string như `audience` và `responsible_department`;
- kiểm tra publish invariant;
- giữ stable keys cho ingestion.

`effective_date` nếu còn xuất hiện trong YAML chỉ là input để service tạo
`document_recipients.effective_date`; không map sang cột `document_versions`.

## Chunk DTO

`Chunk` cần giữ contract logic, không giữ ORM relation:

```text
document_key, version_key
chunk_key, parent_chunk_key
chunk_index, chunk_type
content, heading_path
page_start, page_end, token_count
metadata
```

Validation tối thiểu:

- Parent không có `parent_chunk_key`.
- Child bắt buộc có `parent_chunk_key`.
- `page_start <= page_end` khi cả hai tồn tại.
- key/content không rỗng; index và token count không âm.

Structural metadata nằm trong `Chunk.metadata` khi đi qua parser/chunker. PostgreSQL MVP chỉ lưu
các cột canonical trong Contract 10; Qdrant mapper lấy structural fields từ DTO này.

## Asset DTO

Giữ `AssetMetadata` và relation DTO đúng các field có persistence consumer. Relation dùng stable
`asset_key` ở boundary; service/repository resolve sang `asset_id`.

## Thứ tự triển khai

1. Chốt enum đang được code và frontmatter dùng.
2. Cập nhật schema nhỏ nhất cần cho use case hiện tại.
3. Cập nhật reader/service mapper.
4. Cập nhật API response DTO nếu output thay đổi.
5. Viết test validation trước khi đổi ORM hoặc migration.

## Validation

Test ít nhất:

- metadata hợp lệ đọc được từ một canonical Markdown thật;
- enum sai bị reject;
- published nhưng chưa `done/approved` bị reject;
- Child thiếu Parent key bị reject;
- page range đảo bị reject;
- DTO dump không chứa ORM object hoặc vendor SDK type.

Schema xong khi YAML → DTO → service input có một contract rõ và không lặp physical schema.
