# Phân loại guild implement

## Quy ước phân loại

- `ingestion/`: từ schema, database, đọc/chuẩn hóa tài liệu, chunking, lưu PostgreSQL, embedding, ghi Qdrant và API upload/OCR.
- `retrieval/`: tìm kiếm từ Qdrant/PostgreSQL, fusion/rerank/expansion, RAG answer chain và API trả lời câu hỏi.

## Các quyết định ở ranh giới

- `14_PART_G_EMBEDDING_GUIDE.md` và `15_PART_H_QDRANT_VECTORSTORE_GUIDE.md` nằm trong ingestion vì đây là bước tạo retrieval index.
- `14A_EMBEDDING_RETRIEVAL_SMOKE_TEST_GUIDE.md` nằm trong retrieval vì mục tiêu chính là kiểm tra chất lượng search.
- `17_PART_J_E2E_TEST_AND_SMOKE_GUIDE.md` nằm trong ingestion vì nó kiểm tra pipeline ingest + DB + Qdrant trước khi answer chain hoàn chỉnh.
- `22_CHUNKING_RETRIEVAL_RECONCILIATION_GUIDE.md` nằm trong retrieval vì contract cuối tập trung vào eligibility, fusion, expansion và query decision; dù có tham chiếu chunking.
- Các guide nền tảng API, runtime, database và checklist được đặt ở ingestion vì chúng cần được hoàn tất trước khi retrieval vận hành.
